"""Frozen synthetic facility processes and causal measurement traces.

Extracted without changing equations, noise, event timing or fingerprints.
Physical truth is used by the simulator and evaluator, never by online selection.
"""
from dataclasses import asdict
from functools import lru_cache
import hashlib
import numpy as np

from .facility import CoupledFacility, FacilityConfig, SCENARIOS

ATOMS = tuple(s for s in SCENARIOS if s != 'combined')

class CompositeFacility(CoupledFacility):
    """Combine declared independent synthetic fault modifiers inside the plant."""
    def __init__(self, config, seed, scenario, control):
        self.components = scenario.split('+')
        if any(part not in ATOMS for part in self.components):
            raise ValueError('Only frozen atom combinations')
        super().__init__(config, seed, 'healthy', control)

    def _faults(self, t):
        rows = []
        for component in self.components:
            self._scenario = component
            rows.append(super()._faults(t))
        self._scenario = 'healthy'
        merged = {}
        for key in rows[0]:
            if key == 'controller_stuck':
                merged[key] = np.logical_or.reduce([r[key] for r in rows])
            elif key in ('sensor_bias', 'load_addition'):
                merged[key] = sum(r[key] for r in rows)
            else:
                merged[key] = np.prod([r[key] for r in rows], axis=0)
        return merged

def arrays_digest(values):
    digest = hashlib.sha256()
    for key in sorted(values):
        array = np.asarray(values[key])
        digest.update(key.encode() + str(array.shape).encode() + array.dtype.str.encode())
        digest.update(array.tobytes())
    return digest.hexdigest()

class ProcessTrace:
    """Process evolves independently of inspection; labels never enter actor."""
    def __init__(self, racks, seed, scenario, control):
        self.config = FacilityConfig(racks=racks)
        plant = CompositeFacility(self.config, seed, scenario, control)
        self.seed, self.scenario, self.control = seed, scenario, control
        packets, truth = [], []
        maximum_energy, maximum_electric, peak_input = 0., 0., 0.
        keys = ('rack_temperature_c', 'secondary_supply_c', 'primary_supply_c',
                'contact_temperature_c', 'rack_flow_kg_s',
                'public_sensor_temperature_c', 'severity_proxy')
        arrays = {key: [] for key in keys}
        initial_energy = plant.stored_energy_kj()
        for _ in range(360):
            row = plant.step()
            packets.append(plant.public_telemetry())
            for key in keys:
                arrays[key].append(row[key])
            truth.append([row[k] for k in ('time_s', 'unserved_it_kw', 'source_power_kw',
                         'stored_energy_kj', 'rejected_heat_kw', 'it_power_kw', 'aux_power_kw',
                         'conversion_loss_kw', 'contact_loss_kw')])
            maximum_energy = max(maximum_energy, abs(row['energy_residual_kj']))
            maximum_electric = max(maximum_electric, abs(row['electric_residual_kw']))
            peak_input = max(peak_input, row['source_power_kw'])
        self.arrays = {key: np.stack(value) for key, value in arrays.items()}
        self.arrays['process_scalars'] = np.asarray(truth)
        self.arrays['asset_weights'] = plant.criticality.copy()
        self.packets = packets
        self.fingerprint = arrays_digest(self.arrays)
        self.metadata = {'racks': racks, 'seed': seed, 'scenario': scenario, 'control': control,
                         'numeric_digest': self.fingerprint, 'peak_source_input_MW': peak_input / 1000,
                         'IT_nameplate_MW': racks * 250 / 1000,
                         'GW_supply_design_budget_MW': 1000 if racks == 3200 else None,
                         'maximum_energy_residual_kj': maximum_energy,
                         'maximum_electric_residual_kw': maximum_electric,
                         'initial_energy_kj': initial_energy,
                         'unserved_IT_kwh': sum(r[1] for r in truth) * 5 / 3600}

    def measurement(self, task, tick):
        a, c = self.arrays, self.config
        if task.kind == 'thermal':
            noise = np.random.default_rng(3000000 + self.seed * 10000 + task.index * 361 + tick).normal(0, .1)
            return {'rack_index': task.index, 'temperature_c': float(a['rack_temperature_c'][tick, task.index] + noise)}
        if task.kind == 'electrical':
            return {'pod_index': task.index, 'contact_temperature_c': float(a['contact_temperature_c'][tick, task.index])}
        if task.kind == 'cooling':
            return {'pod_index': task.index, 'pod_flow_kg_s': float(a['rack_flow_kg_s'][tick].reshape(c.pods, 8)[task.index].sum())}
        error = a['public_sensor_temperature_c'][tick] - a['rack_temperature_c'][tick]
        return {'pod_index': task.index, 'controller_sensor_error_c': float(error.reshape(c.pods, 8)[task.index].mean())}

@lru_cache(maxsize=4)
def trace_for(racks, seed, scenario, control):
    return ProcessTrace(racks, seed, scenario, control)

class PhasedTrace(ProcessTrace):
    def __init__(self, seed, scenario, duration, start, fault_rack=None):
        if duration not in (60, 120, 180, 240, 900) or start not in (150, 335, 520, 705):
            raise ValueError('Frozen injection duration and phase required')
        self.config = FacilityConfig(fault_start_s=start, fault_end_s=start + duration, fault_rack=fault_rack)
        self.seed, self.scenario, self.control = seed, scenario, 'feedback'
        plant = CompositeFacility(self.config, seed, scenario, 'feedback')
        keys = ('rack_temperature_c', 'secondary_supply_c', 'primary_supply_c',
            'contact_temperature_c', 'rack_flow_kg_s', 'public_sensor_temperature_c', 'severity_proxy')
        values = {k: [] for k in keys}
        scalar, self.packets = [], []
        initial = plant.stored_energy_kj()
        max_energy, max_electric = 0., 0.
        for _ in range(360):
            row = plant.step()
            self.packets.append(plant.public_telemetry())
            for key in keys:
                values[key].append(row[key])
            scalar.append([row[k] for k in ('time_s', 'unserved_it_kw', 'source_power_kw',
                'stored_energy_kj', 'rejected_heat_kw', 'it_power_kw', 'aux_power_kw',
                'conversion_loss_kw', 'contact_loss_kw')])
            max_energy = max(max_energy, abs(row['energy_residual_kj']))
            max_electric = max(max_electric, abs(row['electric_residual_kw']))
        self.arrays = {k: np.stack(v) for k, v in values.items()}
        self.arrays['process_scalars'] = np.asarray(scalar)
        self.arrays['asset_weights'] = plant.criticality.copy()
        self.fingerprint = arrays_digest(self.arrays)
        self.metadata = {'racks': 128, 'seed': seed, 'scenario': scenario, 'control': 'feedback',
            'fault_duration_s': duration, 'fault_start_s': start, 'configuration': asdict(self.config),
            'numeric_digest': self.fingerprint, 'initial_energy_kj': initial,
            'maximum_energy_residual_kj': max_energy, 'maximum_electric_residual_kw': max_electric,
            'peak_source_input_MW': max(r[2] for r in scalar) / 1000, 'IT_nameplate_MW': 32.,
            'unserved_IT_kwh': sum(r[1] for r in scalar) * 5 / 3600}

@lru_cache(maxsize=32)
def phased_trace(seed, scenario, duration, start, fault_rack=None):
    return PhasedTrace(seed, scenario, duration, start, fault_rack)
