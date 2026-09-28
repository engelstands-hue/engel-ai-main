'''Single fail-closed runtime budget contract for Engel model training.'''
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = 'engel_training_cycle_runtime_contract_v1'
CONTRACT_PATH = Path(__file__).with_suffix('.contract')
LANE_ORDER = ('slm', 'llm')
LANE_STEPS = {
    'slm': ('dataset', 'train', 'verify'),
    'llm': ('dataset', 'preflight', 'train_and_evaluate'),
}
WHOLE_CYCLE_KEYS = {
    ('slm',): 'slm',
    ('llm',): 'llm',
    ('slm', 'llm'): 'slm_llm',
}
MAX_REVIEWED_SECONDS = 7 * 24 * 60 * 60


class RuntimeContractError(ValueError):
    '''The reviewed model-cycle timeout contract is absent or malformed.'''


def normalize_targets(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        raw = value.split(',')
    elif isinstance(value, (list, tuple)) and all(
        isinstance(item, str) for item in value
    ):
        raw = list(value)
    else:
        raise RuntimeContractError(
            'training targets must be a string or string list'
        )
    selected = {item.strip().casefold() for item in raw if item.strip()}
    unsupported = sorted(selected - set(LANE_ORDER))
    if unsupported:
        raise RuntimeContractError(
            'unsupported training target(s): ' + ', '.join(unsupported)
        )
    if not selected:
        raise RuntimeContractError('at least one training target is required')
    return tuple(lane for lane in LANE_ORDER if lane in selected)


def validate_contract(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get('schema') != SCHEMA:
        raise RuntimeContractError(
            'model-training runtime contract schema is invalid'
        )
    lanes = payload.get('lanes')
    whole_cycle = payload.get('whole_cycle_seconds')
    termination_grace = payload.get('termination_grace_seconds')
    if (
        not isinstance(termination_grace, int)
        or isinstance(termination_grace, bool)
        or not 1 <= termination_grace <= 3600
    ):
        raise RuntimeContractError('termination_grace_seconds is outside 1..3600')
    if not isinstance(lanes, dict) or set(lanes) != set(LANE_ORDER):
        raise RuntimeContractError(
            'runtime contract must define exactly slm and llm lanes'
        )
    for lane in LANE_ORDER:
        steps = lanes.get(lane)
        if not isinstance(steps, dict) or set(steps) != set(LANE_STEPS[lane]):
            raise RuntimeContractError(
                f'runtime contract lane {lane} step set/order is invalid'
            )
        for name, seconds in steps.items():
            if not isinstance(name, str) or not name.strip():
                raise RuntimeContractError(
                    f'runtime contract lane {lane} has an invalid step'
                )
            if (
                not isinstance(seconds, int)
                or isinstance(seconds, bool)
                or not 1 <= seconds <= MAX_REVIEWED_SECONDS
            ):
                raise RuntimeContractError(
                    f'runtime contract {lane}.{name} must be a positive integer'
                )
    if (
        not isinstance(whole_cycle, dict)
        or set(whole_cycle) != {'slm', 'llm', 'slm_llm'}
    ):
        raise RuntimeContractError('whole-cycle limits must define slm, llm, and slm_llm')
    for key, seconds in whole_cycle.items():
        if (
            not isinstance(seconds, int)
            or isinstance(seconds, bool)
            or not 1 <= seconds <= MAX_REVIEWED_SECONDS
        ):
            raise RuntimeContractError(f'whole-cycle limit {key} is invalid')
    if not (
        whole_cycle['slm'] >= sum(lanes['slm'].values())
        and whole_cycle['llm'] >= sum(lanes['llm'].values())
        and whole_cycle['slm_llm']
        >= sum(lanes['slm'].values()) + sum(lanes['llm'].values())
    ):
        raise RuntimeContractError('whole-cycle limit is shorter than its lane steps')
    return payload


def load_contract(path: Path | str = CONTRACT_PATH) -> dict[str, Any]:
    contract_path = Path(path)
    try:
        lines = contract_path.read_text(encoding='utf-8-sig').splitlines()
    except OSError as exc:
        raise RuntimeContractError(
            f'model-training runtime contract is unreadable: {exc}'
        ) from exc
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise RuntimeContractError(
                f'malformed runtime contract line {line_number}'
            )
        key, value = (part.strip() for part in line.split('=', 1))
        if not key or not value or key in values:
            raise RuntimeContractError(
                f'invalid or duplicate runtime contract key at line {line_number}'
            )
        values[key] = value
    expected = {
        'schema',
        'termination_grace_seconds',
        'whole_cycle.slm',
        'whole_cycle.llm',
        'whole_cycle.slm_llm',
        'slm.dataset',
        'slm.train',
        'slm.verify',
        'llm.dataset',
        'llm.preflight',
        'llm.train_and_evaluate',
    }
    if set(values) != expected:
        raise RuntimeContractError(
            'runtime contract keys differ from the reviewed schema'
        )
    try:
        payload = {
            'schema': values['schema'],
            'termination_grace_seconds': int(values['termination_grace_seconds']),
            'whole_cycle_seconds': {
                'slm': int(values['whole_cycle.slm']),
                'llm': int(values['whole_cycle.llm']),
                'slm_llm': int(values['whole_cycle.slm_llm']),
            },
            'lanes': {
                lane: {
                    key.split('.', 1)[1]: int(value)
                    for key, value in values.items()
                    if key.startswith(lane + '.')
                }
                for lane in LANE_ORDER
            },
        }
    except ValueError as exc:
        raise RuntimeContractError(
            'runtime contract timeout values must be integers'
        ) from exc
    return validate_contract(payload)


def deadline_seconds(
    targets: Any,
    contract: dict[str, Any] | None = None,
) -> int:
    selected = normalize_targets(targets)
    payload = load_contract() if contract is None else validate_contract(contract)
    return int(payload['whole_cycle_seconds'][WHOLE_CYCLE_KEYS[selected]])


def termination_grace_seconds(
    contract: dict[str, Any] | None = None,
) -> int:
    payload = load_contract() if contract is None else validate_contract(contract)
    return int(payload['termination_grace_seconds'])


def step_timeout_seconds(lane: str, step: str) -> int:
    payload = load_contract()
    try:
        return int(payload['lanes'][lane][step])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeContractError(
            f'unknown runtime step: {lane}.{step}'
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--targets', required=True)
    parser.add_argument('--contract', default=str(CONTRACT_PATH))
    args = parser.parse_args()
    contract = load_contract(args.contract)
    targets = normalize_targets(args.targets)
    print(
        json.dumps(
            {
                'schema': SCHEMA,
                'targets': list(targets),
                'deadline_seconds': deadline_seconds(targets, contract),
                'termination_grace_seconds': termination_grace_seconds(contract),
                'contract_path': str(Path(args.contract).resolve()),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
