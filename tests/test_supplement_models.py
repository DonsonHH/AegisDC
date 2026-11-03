import unittest
from unittest.mock import patch

import numpy as np

try:
    import torch
except ImportError:
    torch = None


@unittest.skipIf(torch is None, 'Optional isolated Torch runtime is required for neural model checks')
class SupplementalModelTests(unittest.TestCase):
    def test_untrained_residual_preserves_exact_nominal_and_uses_no_posterior(self):
        from patrol_rsi.supplement_models import FrozenTemperaturePredictor, ResidualConditionalUNet
        torch.manual_seed(900002)
        model = ResidualConditionalUNet()
        nominal = np.linspace(45.123456789, 75.987654321, 128)
        context = np.zeros((57, 8, 16), np.float32)
        with patch.object(model.posterior, 'forward', side_effect=AssertionError('Online inference used the supervised posterior')):
            predicted = FrozenTemperaturePredictor(model, 'cpu')(context, nominal)
        np.testing.assert_array_equal(predicted, nominal)

    def test_policy_masks_a_candidate_even_when_it_has_larger_logit(self):
        from patrol_rsi.supplement_models import BenchmarkPolicy
        policy = BenchmarkPolicy()
        with patch.object(policy.actor, 'forward', return_value=torch.tensor([[0.], [1000.]])):
            distribution = policy.distribution(torch.zeros(2, 21), torch.tensor([True, False]))
        np.testing.assert_array_equal(distribution.probs.detach().numpy(), [1., 0.])


if __name__ == '__main__':
    unittest.main()
