"""Resume policy training from completed ledger entries, not partial saves."""
from pathlib import Path


def completed_policy_prefix(entries, estimator, seed, maximum=120):
    prefix = f'{estimator}-{seed}-'
    numbers = set()
    for row in entries:
        if row['phase'] == 'ppo_train' and row['status'] == 'completed' and row['id'].startswith(prefix):
            number = int(row['id'][len(prefix):])
            if not 1 <= number <= maximum:
                raise RuntimeError('Completed PPO episode lies outside the registered budget')
            numbers.add(number)
    completed = 0
    while completed+1 in numbers:
        completed += 1
    if any(number > completed for number in numbers):
        raise RuntimeError('PPO completion ledger has a gap; do not skip an uncompleted episode')
    return completed


def select_policy_resume_checkpoint(current, previous, completed):
    """A save one episode ahead of the ledger is retained and rolled back."""
    if current is None:
        if completed:
            raise RuntimeError('Completed PPO ledger has no checkpoint')
        return None
    if current['episodes'] == completed:
        return current
    if current['episodes'] == completed+1:
        if completed == 0:
            return None  # Recreate paired seeded initialization for episode1.
        if previous is not None and previous['episodes'] == completed:
            return previous
        raise RuntimeError('Uncommitted PPO save has no matching previous checkpoint')
    raise RuntimeError('PPO checkpoint episode count does not match completed ledger prefix')


def policy_state_files(output, estimator, seed):
    output = Path(output)
    name = f'ppo-{estimator}-{seed}'
    return {'history':output/'training'/(name+'.json'), 'checkpoint':output/'checkpoints'/(name+'.pt'),
            'previous':output/'checkpoint-recovery'/(name+'.pt')}
