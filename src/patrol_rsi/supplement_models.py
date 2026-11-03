"""Small temperature-adapted conditional latent U-Net; not the water-paper model."""
import numpy as np
import torch
from torch.distributions import Categorical
from torch import nn
from torch.nn import functional as F

from .supplement_task import BENCHMARK_FEATURES, from_grid


def conv_block(inputs,outputs):
    return nn.Sequential(nn.Conv2d(inputs,outputs,3,padding=1),nn.GroupNorm(4,outputs),nn.SiLU(),
                         nn.Conv2d(outputs,outputs,3,padding=1),nn.GroupNorm(4,outputs),nn.SiLU())


class ResidualConditionalUNet(nn.Module):
    """Conditional prior/posterior and two spatial skip levels on an8x16 grid."""
    def __init__(self,channels=57,width=16,latent=16):
        super().__init__();self.channels=channels;self.width=width;self.latent=latent
        self.first=conv_block(channels,width)
        self.second=conv_block(width,width*2)
        self.bottom=conv_block(width*2,width*4)
        self.prior=nn.Linear(width*4*2*4,latent*2)
        self.posterior=nn.Sequential(conv_block(channels+1,width),nn.AvgPool2d(2),
            conv_block(width,width*2),nn.AvgPool2d(2),nn.Flatten(),nn.Linear(width*2*2*4,latent*2))
        self.latent_map=nn.Linear(latent,width*4*2*4)
        self.fuse=conv_block(width*8,width*4)
        self.up_second=conv_block(width*6,width*2)
        self.up_first=conv_block(width*3,width)
        self.output=nn.Conv2d(width,1,1)
        nn.init.zeros_(self.output.weight);nn.init.zeros_(self.output.bias)

    @staticmethod
    def distribution(raw):
        mu,logvar=raw.chunk(2,dim=1)
        return mu,logvar.clamp(-8,4)

    def encode(self,context):
        first=self.first(context);second=self.second(F.avg_pool2d(first,2))
        bottom=self.bottom(F.avg_pool2d(second,2))
        prior=self.distribution(self.prior(bottom.flatten(1)))
        return first,second,bottom,prior

    def decode(self,encoded,z):
        first,second,bottom,_=encoded
        latent=self.latent_map(z).reshape(z.shape[0],self.width*4,2,4)
        value=self.fuse(torch.cat((bottom,latent),dim=1))
        value=self.up_second(torch.cat((F.interpolate(value,size=second.shape[-2:],mode='nearest'),second),dim=1))
        value=self.up_first(torch.cat((F.interpolate(value,size=first.shape[-2:],mode='nearest'),first),dim=1))
        return self.output(value)

    def prediction(self,context):
        encoded=self.encode(context)
        return context[:,-1:]+self.decode(encoded,encoded[3][0])

    def loss(self,context,target,weights,beta):
        encoded=self.encode(context);prior=encoded[3]
        posterior=self.distribution(self.posterior(torch.cat((context,target),dim=1)))
        z=posterior[0]+torch.randn_like(posterior[0])*torch.exp(posterior[1]/2)
        sampled=context[:,-1:]+self.decode(encoded,z)
        predicted=context[:,-1:]+self.decode(encoded,prior[0])
        # Train the operational prior mean as well as the variational path.
        reconstruction=(((sampled-target).square()+(predicted-target).square())*.5*weights).mean()/weights.mean()
        kl=.5*(prior[1]-posterior[1]+(posterior[1].exp()+(posterior[0]-prior[0]).square())/prior[1].exp()-1).mean()
        return reconstruction+beta*kl,reconstruction.detach(),kl.detach()


class FrozenTemperaturePredictor:
    def __init__(self,model,device):
        self.model=model.eval();self.device=torch.device(device);self.calls=0

    def __call__(self,public_context,nominal):
        if np.asarray(public_context).shape!=(57,8,16):raise ValueError('Only declared public57-channel grid is accepted')
        if self.device.type=='cuda':torch.cuda.synchronize(self.device)
        with torch.inference_mode():
            context=torch.as_tensor(np.array(public_context,copy=True),dtype=torch.float32,device=self.device).unsqueeze(0)
            residual=(self.model.prediction(context)-context[:,-1:])[0,0].detach().cpu().numpy()
        if self.device.type=='cuda':torch.cuda.synchronize(self.device)
        self.calls+=1
        return np.asarray(nominal,dtype=float)+from_grid(residual).astype(float)*20


def load_temperature_predictor(path,device='cuda'):
    pack=torch.load(path,map_location='cpu',weights_only=True)
    model=ResidualConditionalUNet(**pack['architecture']);model.load_state_dict(pack['state_dict']);model.to(device)
    return FrozenTemperaturePredictor(model,device)


class BenchmarkPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        self.actor=nn.Sequential(nn.Linear(len(BENCHMARK_FEATURES),32),nn.Tanh(),nn.Linear(32,32),nn.Tanh(),nn.Linear(32,1))
        self.critic=nn.Sequential(nn.Linear(10,32),nn.Tanh(),nn.Linear(32,32),nn.Tanh(),nn.Linear(32,1))

    def distribution(self,features,mask):
        if not mask.any(dim=-1).all():raise ValueError('At least one legal candidate required')
        return Categorical(logits=self.actor(features).squeeze(-1).masked_fill(~mask,-1e9))

    def values(self,public):return self.critic(public).squeeze(-1)


def update_policy(model,optimizer,rollout):
    """One complete episode; shared/team PPO with the frozen21/10 schema."""
    if len(rollout)!=359:raise ValueError('PPO update requires one complete359-step episode')
    rewards=np.asarray([r['reward'] for r in rollout],dtype=np.float32)
    values=np.asarray([r['value'] for r in rollout],dtype=np.float32)
    advantage=np.zeros(359,dtype=np.float32);carry=following=0.
    for step in reversed(range(359)):
        delta=rewards[step]+.99*following-values[step]
        carry=delta+.99*.95*carry;advantage[step]=carry;following=values[step]
    returns=torch.as_tensor(advantage+values);normalized=torch.as_tensor((advantage-advantage.mean())/(advantage.std()+1e-8))
    samples=[(step,s) for step,r in enumerate(rollout) for s in r['samples']]
    width=max(len(row['features']) for _,row in samples)
    features=np.zeros((len(samples),width,len(BENCHMARK_FEATURES)),dtype=np.float32);masks=np.zeros((len(samples),width),dtype=bool)
    actions=[];groups=[]
    for index,(step,row) in enumerate(samples):
        count=len(row['features']);features[index,:count]=row['features'];masks[index,:count]=row['mask'];actions.append(row['action']);groups.append(step)
    features=torch.as_tensor(features);masks=torch.as_tensor(masks);actions=torch.as_tensor(actions);groups=torch.as_tensor(groups)
    old=torch.as_tensor([r['logprob'] for r in rollout]);public=torch.as_tensor(np.stack([r['public_value'] for r in rollout]));losses=[]
    for _ in range(4):
        distribution=model.distribution(features,masks)
        logs=torch.zeros(359).index_add(0,groups,distribution.log_prob(actions))
        entropy=torch.zeros(359).index_add(0,groups,distribution.entropy())
        counts=torch.zeros(359).index_add(0,groups,torch.ones(len(groups)))
        ratio=torch.exp((logs-old).clamp(-15,15))
        actor=-torch.minimum(ratio*normalized,ratio.clamp(.8,1.2)*normalized).mean()
        critic=(model.values(public)-returns).square().mean()
        loss=actor+.5*critic-.01*(entropy/counts.clamp_min(1)).mean()
        if not torch.isfinite(loss):raise RuntimeError('Nonfinite supplementary PPO loss')
        optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),.5);optimizer.step();losses.append(float(loss.detach()))
    return {'losses':losses,'task_choices':len(samples),'choice_sets_with_alternatives':sum(len(s['features'])>1 for _,s in samples),
            'mean_public_reward':float(rewards.mean()),'total_public_reward':float(rewards.sum())}
