#!/usr/bin/env python3
'''Verify the shared Python/Flutter model-cycle runtime budget contract.'''
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import engel_training_cycle_runtime_contract as runtime_contract
import run_engel_real_training_cycle as real_cycle


checks: list[dict[str, object]] = []


def check(name: str, ok: bool, detail: object) -> None:
    checks.append(
        {
            'name': name,
            'status': 'PASS' if ok else 'FAIL',
            'detail': detail,
        }
    )


contract = runtime_contract.load_contract()
deadlines = {
    target: runtime_contract.deadline_seconds(target, contract)
    for target in ('slm', 'llm', 'slm,llm')
}
corpus_plan = real_cycle.inspect_construction_corpus_bundle(
    ROOT / 'memory' / 'training' / 'construction_env',
    'runtime_contract_verify',
)
corpus_files = len(corpus_plan.get('files') or [])
common_external = (
    real_cycle.TIMEOUT_PROBE
    + (2 * real_cycle.TIMEOUT_SHORT)
    + (len(real_cycle.CT_TOOL_FILES) * real_cycle.TIMEOUT_SCP)
    + (2 * real_cycle.TIMEOUT_SHORT)
    + (len(real_cycle.CANONICAL_CURRICULA) * real_cycle.TIMEOUT_SCP)
    + (4 * real_cycle.TIMEOUT_SHORT)
    + (corpus_files * real_cycle.TIMEOUT_SCP)
)
slm_artifacts = len(real_cycle.slm_roster.KNOWN_TASKS) + 1
slm_external = (
    real_cycle.TIMEOUT_SLM_DATASETS
    + real_cycle.TIMEOUT_SLM_TRAIN
    + real_cycle.TIMEOUT_SLM_VERIFY
    + (5 * real_cycle.TIMEOUT_SHORT)
    + (slm_artifacts * real_cycle.TIMEOUT_SCP)
)
llm_external = (
    real_cycle.TIMEOUT_DATASET_BUILD
    + real_cycle.TIMEOUT_LLM_PREFLIGHT
    + real_cycle.TIMEOUT_LLM_TRAIN
    + (3 * real_cycle.TIMEOUT_SHORT)
)
reviewed_minima = {
    'slm': common_external + slm_external,
    'llm': common_external + llm_external,
    'slm,llm': common_external + slm_external + llm_external,
}
check(
    'whole_cycle_deadlines_cover_reviewed_end_to_end_external_caps',
    deadlines == {'slm': 28800, 'llm': 46800, 'slm,llm': 57600}
    and corpus_plan.get('ok') is True
    and all(
        deadlines[target] >= minimum
        for target, minimum in reviewed_minima.items()
    ),
    {
        'deadlines': deadlines,
        'reviewed_minima': reviewed_minima,
        'tool_files': len(real_cycle.CT_TOOL_FILES),
        'pack_files': len(real_cycle.CANONICAL_CURRICULA),
        'corpus_files': corpus_files,
        'slm_artifacts': slm_artifacts,
    },
)
check(
    'retired_ui_limits_are_below_the_reviewed_safe_deadlines',
    deadlines['slm'] > 45 * 60
    and deadlines['llm'] > 4 * 60 * 60
    and deadlines['slm,llm'] > deadlines['llm'],
    deadlines,
)

malformed_refused = 0
for payload in (
    {},
    {'schema': runtime_contract.SCHEMA},
    {
        **contract,
        'termination_grace_seconds': 0,
    },
    {
        **contract,
        'whole_cycle_seconds': {
            **contract['whole_cycle_seconds'],
            'slm': 0,
        },
    },
    {
        **contract,
        'lanes': {**contract['lanes'], 'slm': {'dataset': 0}},
    },
):
    try:
        runtime_contract.validate_contract(payload)
    except runtime_contract.RuntimeContractError:
        malformed_refused += 1
check(
    'malformed_contracts_fail_closed',
    malformed_refused == 5,
    {'refused': malformed_refused, 'probes': 5},
)

expected_step_timeouts = {
    'slm.dataset': runtime_contract.step_timeout_seconds('slm', 'dataset'),
    'slm.train': runtime_contract.step_timeout_seconds('slm', 'train'),
    'slm.verify': runtime_contract.step_timeout_seconds('slm', 'verify'),
    'llm.dataset': runtime_contract.step_timeout_seconds('llm', 'dataset'),
    'llm.preflight': runtime_contract.step_timeout_seconds('llm', 'preflight'),
    'llm.train_and_evaluate': runtime_contract.step_timeout_seconds(
        'llm', 'train_and_evaluate'
    ),
}
actual_step_timeouts = {
    'slm.dataset': real_cycle.TIMEOUT_SLM_DATASETS,
    'slm.train': real_cycle.TIMEOUT_SLM_TRAIN,
    'slm.verify': real_cycle.TIMEOUT_SLM_VERIFY,
    'llm.dataset': real_cycle.TIMEOUT_DATASET_BUILD,
    'llm.preflight': real_cycle.TIMEOUT_LLM_PREFLIGHT,
    'llm.train_and_evaluate': real_cycle.TIMEOUT_LLM_TRAIN,
}
real_cycle_source = (
    ROOT / 'tools' / 'run_engel_real_training_cycle.py'
).read_text(encoding='utf-8')
check(
    'orchestrator_consumes_contract_and_clamps_every_child_process',
    actual_step_timeouts == expected_step_timeouts
    and '_ACTIVE_CYCLE_DEADLINE_MONOTONIC' in real_cycle_source
    and 'timeout_s = _bounded_cycle_timeout(requested_timeout)' in real_cycle_source
    and 'runtime_budget.deadline_seconds(' in real_cycle_source
    and 'child_timeouts_clamped_to_deadline' in real_cycle_source,
    {
        'expected_step_timeouts': expected_step_timeouts,
        'actual_step_timeouts': actual_step_timeouts,
    },
)

flutter_source = (
    ROOT / 'engel_flutter_main' / 'lib' / 'training_section.dart'
).read_text(encoding='utf-8')
check(
    'flutter_consumes_the_shared_contract_and_has_no_retired_literal_limits',
    'engel_training_cycle_runtime_contract.contract' in flutter_source
    and '_readModelTrainingRuntimeBudget' in flutter_source
    and 'normalizeEngelModelTrainingTargets' in flutter_source
    and "'--targets',\n      canonicalTrainingTargets" in flutter_source
    and 'Timer(runtimeBudget.clientDeadline' in flutter_source
    and '_enforceModelTrainingDeadline' in flutter_source
    and 'await process.exitCode.timeout(budget.terminationGrace)' in flutter_source
    and 'Duration(hours: 4)' not in flutter_source
    and 'Duration(minutes: 45)' not in flutter_source,
    'Flutter must parse the shared contract and verify termination after its grace',
)

main_source = (
    ROOT / 'engel_flutter_main' / 'lib' / 'main.dart'
).read_text(encoding='utf-8')
check(
    'flutter_disposal_stops_the_owned_model_training_process',
    '_disposeModelTrainingCycleGuard();' in main_source
    and 'process.stopTree()' in flutter_source
    and 'CRITICAL: model training termination unconfirmed' in flutter_source,
    'App disposal and deadline expiry must not orphan an owned training process',
)

test_source = (
    ROOT / 'engel_flutter_main' / 'test' / 'widget_test.dart'
).read_text(encoding='utf-8')
check(
    'flutter_behavioral_tests_cover_slm_llm_both_and_missing_contract',
    all(
        marker in test_source
        for marker in (
            'expect(slm.wholeCycleDeadline, const Duration(seconds: 28800))',
            'expect(llm.wholeCycleDeadline, const Duration(seconds: 46800))',
            'expect(both.wholeCycleDeadline, const Duration(seconds: 57600))',
            "normalizeEngelModelTrainingTargets(' LLM, slm,llm ')",
            'Model Training refuses a missing runtime contract',
            'Model Training confirms process exit after its deadline',
            'Model Training keeps controls locked when stop is unconfirmed',
            'Model Training surfaces a process-tree stop exception',
            'Model Training refuses to claim a stop without process exit',
            'Disposing Engel must stop its owned model-training process tree.',
        )
    ),
    'widget_test.dart carries the cross-language contract regressions',
)

failed = [item for item in checks if item['status'] != 'PASS']
print(
    json.dumps(
        {
            'schema': 'engel_training_cycle_runtime_contract_verifier_v1',
            'status': 'FAIL' if failed else 'PASS',
            'passed': len(checks) - len(failed),
            'total': len(checks),
            'failed': [item['name'] for item in failed],
            'checks': checks,
        },
        indent=2,
        sort_keys=True,
    )
)
raise SystemExit(1 if failed else 0)
