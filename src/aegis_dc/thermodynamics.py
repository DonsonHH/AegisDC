"""Replaceable, domain-limited pure-fluid property boundary for engineering runs.

Only frozen JSON is read. No authoring program or external EOS is imported.
The fixed-volume flash searches every interpolation segment, including possible
interior roots, and refuses absent or nonunique two-phase solutions.
"""
from bisect import bisect_right
from hashlib import sha256
import math
from pathlib import Path

from patrol_rsi.contracts import strict_json

PRIMITIVES = ('T_sat_K', 'v_l_m3_kg', 'v_v_m3_kg', 'u_l_J_kg', 'u_v_J_kg')


def finite_number(value, label, *, positive=False):
    """Reject booleans, unrepresentable and nonfinite public numerical inputs."""
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid or (positive and value <= 0):
        raise ValueError(label + ' must be a finite' + (' positive' if positive else '') + ' number')
    return float(value)


class SaturationTable:
    """ln(p) interpolation of T/v/u with rho and h derived consistently."""

    def __init__(self, document, content_sha256):
        if document.get('schema') != 'aegisdc-reference-saturation-v1':
            raise ValueError('Unknown saturation table schema')
        self.rows = document['rows']
        if len(self.rows) < 2:
            raise ValueError('Saturation table needs at least two rows')
        previous = 0.0
        for row in self.rows:
            for key in ('p_Pa',) + PRIMITIVES:
                finite_number(row[key], 'Property ' + key, positive=True)
            if not (row['p_Pa'] > previous and row['v_v_m3_kg'] > row['v_l_m3_kg']
                    and row['u_v_J_kg'] > row['u_l_J_kg']):
                raise ValueError('Invalid saturation order or two-phase separation')
            previous = row['p_Pa']
        self.pressures = [row['p_Pa'] for row in self.rows]
        self.logs = [math.log(p) for p in self.pressures]
        self.sha256 = content_sha256
        self.source = document['source']
        self.validity = document['validity']

    @classmethod
    def from_file(cls, path, *, expected_sha256=None):
        content = Path(path).read_bytes()
        identity = sha256(content).hexdigest()
        if expected_sha256 is not None and identity != expected_sha256:
            raise ValueError('Frozen property table SHA-256 mismatch')
        return cls(strict_json(content.decode('utf-8')), identity)

    def at_pressure(self, pressure_Pa):
        p = finite_number(pressure_Pa, 'Pressure', positive=True)
        if not self.pressures[0] <= p <= self.pressures[-1]:
            raise ValueError('Pressure outside saturation table domain; no extrapolation')
        i = min(bisect_right(self.pressures, p) - 1, len(self.rows) - 2)
        fraction = (math.log(p) - self.logs[i]) / (self.logs[i + 1] - self.logs[i])
        a, b = self.rows[i], self.rows[i + 1]
        result = {key: a[key] + fraction * (b[key] - a[key]) for key in PRIMITIVES}
        result.update(pressure_Pa=p, temperature_K=result['T_sat_K'])
        for phase in ('l', 'v'):
            volume = result['v_' + phase + '_m3_kg']
            result['rho_' + phase + '_kg_m3'] = 1 / volume
            result['h_' + phase + '_J_kg'] = result['u_' + phase + '_J_kg'] + p * volume
        return result

    def flash(self, mass_kg, internal_energy_J, volume_m3):
        mass = finite_number(mass_kg, 'Refrigerant mass', positive=True)
        energy = finite_number(internal_energy_J, 'Refrigerant internal energy')
        volume = finite_number(volume_m3, 'Refrigerant volume', positive=True)
        specific_volume, target = volume / mass, energy / mass
        roots = []
        for i, (a, b) in enumerate(zip(self.rows, self.rows[1:])):
            vl, vv = a['v_l_m3_kg'], a['v_v_m3_kg']
            ul, uv = a['u_l_J_kg'], a['u_v_J_kg']
            dvl, dvv = b['v_l_m3_kg'] - vl, b['v_v_m3_kg'] - vv
            dul, duv = b['u_l_J_kg'] - ul, b['u_v_J_kg'] - uv
            # Multiply u_mix-target by the strictly positive v_v-v_l.
            c0 = (ul - target) * (vv - vl) + (specific_volume - vl) * (uv - ul)
            c1 = dul * (vv - vl) + (ul - target) * (dvv - dvl) \
                - dvl * (uv - ul) + (specific_volume - vl) * (duv - dul)
            c2 = dul * (dvv - dvl) - dvl * (duv - dul)
            candidates = []
            # Independently check the closed segment endpoints. A polynomial
            # root can round just beyond [0, 1] even for an exact endpoint
            # inventory. Accept only an already admissible quality and an
            # endpoint energy match within floating-point evaluation error;
            # this neither clips quality nor moves an out-of-domain root.
            for endpoint, row in ((0.0, a), (1.0, b)):
                x = (specific_volume - row['v_l_m3_kg']) / (row['v_v_m3_kg'] - row['v_l_m3_kg'])
                if 0 <= x <= 1:
                    endpoint_energy = (1 - x) * row['u_l_J_kg'] + x * row['u_v_J_kg']
                    if abs(endpoint_energy - target) <= 8 * max(math.ulp(endpoint_energy), math.ulp(target)):
                        candidates.append(endpoint)
            if c2 == 0:
                if c1 != 0:
                    candidates.append(-c0 / c1)
                elif c0 == 0:
                    raise ValueError('Nonunique two-phase flash on an interpolation segment')
            else:
                discriminant = c1 * c1 - 4 * c2 * c0
                if discriminant >= 0:
                    q = -0.5 * (c1 + math.copysign(math.sqrt(discriminant), c1))
                    if q != 0:
                        candidates.extend((q / c2, c0 / q))
                    else:
                        candidates.append(-c1 / (2 * c2))
            for fraction in candidates:
                if not 0 <= fraction <= 1:
                    continue
                p = (self.pressures[i] if fraction == 0 else self.pressures[i + 1]
                     if fraction == 1 else math.exp(self.logs[i] + fraction * (self.logs[i + 1] - self.logs[i])))
                # exp(log(endpoint)) can land one ulp beyond a table endpoint.
                # Only roundoff in a coordinate already inside this segment is
                # corrected. Quality and an out-of-domain physical root are
                # never clipped.
                if p < self.pressures[i] and math.isclose(p, self.pressures[i], rel_tol=1e-14):
                    p = self.pressures[i]
                if p > self.pressures[i + 1] and math.isclose(p, self.pressures[i + 1], rel_tol=1e-14):
                    p = self.pressures[i + 1]
                props = self.at_pressure(p)
                quality = (specific_volume - props['v_l_m3_kg']) / \
                    (props['v_v_m3_kg'] - props['v_l_m3_kg'])
                if not 0 <= quality <= 1:
                    continue
                residual = (1 - quality) * props['u_l_J_kg'] + quality * props['u_v_J_kg'] - target
                if abs(residual) > 1e-6:
                    continue
                if not any(math.isclose(p, found['pressure_Pa'], rel_tol=1e-10) for found in roots):
                    roots.append(dict(props, quality=quality,
                                      liquid_mass_kg=mass * (1 - quality), vapor_mass_kg=mass * quality,
                                      mass_kg=mass, internal_energy_J=energy, volume_m3=volume,
                                      specific_energy_residual_J_kg=residual))
        if len(roots) != 1:
            raise ValueError('Two-phase M/U/V flash requires exactly one domain-valid root; found ' + str(len(roots)))
        return roots[0]
