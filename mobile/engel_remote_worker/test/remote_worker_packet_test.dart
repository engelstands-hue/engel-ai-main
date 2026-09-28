import 'package:engel_remote_worker/remote_worker_packet.dart';
import 'package:flutter_test/flutter_test.dart';

const manualTaskPacketExample = '''
{
  "packet_version": "1",
  "packet_id": "manual-test-001",
  "created_by": "Engel Communication Queen",
  "trust_level": "untrusted_until_reviewed",
  "task_type": "summarize_text",
  "title": "Manual safe task",
  "instructions": "Do not execute commands. Draft notes only.",
  "allowed_outputs": ["draft_result_json"],
  "blocked_actions": [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes"
  ]
}
''';

const engelReviewPacketExample = '''
{
  "packet_version": "1",
  "packet_id": "engel-review-001",
  "created_by": "Engel Communication Queen",
  "trust_level": "untrusted_until_reviewed",
  "task_type": "review_status",
  "title": "Engel review",
  "instructions": "Review only.",
  "target_system": "Engel",
  "allowed_outputs": ["draft_result_json"],
  "blocked_actions": [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes"
  ]
}
''';

const superSwarmReviewPacketExample = '''
{
  "packet_version": "1",
  "packet_id": "super-swarm-review-001",
  "created_by": "Engel Communication Queen",
  "trust_level": "untrusted_until_reviewed",
  "task_type": "review_status",
  "title": "Super Swarm review",
  "instructions": "Review only.",
  "target_system": "Super Swarm",
  "allowed_outputs": ["draft_result_json"],
  "blocked_actions": [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes"
  ]
}
''';

void main() {
  test('valid packet parses', () {
    final result = RemoteWorkerPacket.parse(manualTaskPacketExample);

    expect(result.isSuccess, isTrue);
    expect(result.packet!.packetId, 'manual-test-001');
    expect(result.packet!.hasAllRequiredBlockedActions, isTrue);
  });

  test('invalid JSON fails safely', () {
    final result = RemoteWorkerPacket.parse('{not json');

    expect(result.isSuccess, isFalse);
    expect(result.error, contains('Invalid JSON'));
  });

  test('missing packet_id creates warning', () {
    final result = RemoteWorkerPacket.parse('''
{
  "title": "Missing id",
  "trust_level": "untrusted",
  "blocked_actions": [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes"
  ]
}
''');

    expect(result.packet!.validationWarnings, contains('Missing packet_id.'));
  });

  test('missing title creates warning', () {
    final result = RemoteWorkerPacket.parse('''
{
  "packet_id": "missing-title",
  "trust_level": "untrusted",
  "blocked_actions": [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes"
  ]
}
''');

    expect(result.packet!.validationWarnings, contains('Missing title.'));
  });

  test('missing trust_level creates warning', () {
    final result = RemoteWorkerPacket.parse('''
{
  "packet_id": "missing-trust",
  "title": "Missing trust",
  "blocked_actions": [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes"
  ]
}
''');

    expect(result.packet!.validationWarnings, contains('Missing trust_level.'));
  });

  test('missing blocked_actions creates warning', () {
    final result = RemoteWorkerPacket.parse('''
{
  "packet_id": "missing-blocks",
  "title": "Missing blocked actions",
  "trust_level": "untrusted"
}
''');

    expect(
      result.packet!.validationWarnings,
      contains('Missing blocked_actions.'),
    );
  });

  test('missing one required blocked action creates warning', () {
    final result = RemoteWorkerPacket.parse('''
{
  "packet_id": "missing-one-block",
  "title": "Missing one block",
  "trust_level": "untrusted",
  "blocked_actions": [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel"
  ]
}
''');

    expect(
      result.packet!.validationWarnings,
      contains('Missing required blocked action: auto_apply_fixes.'),
    );
  });

  test('Engel target packet gets review-only warning', () {
    final result = RemoteWorkerPacket.parse(engelReviewPacketExample);

    expect(
      result.packet!.validationWarnings,
      contains('Engel target packet is review-only.'),
    );
    expect(result.packet!.isEngelTarget, isTrue);
  });

  test('Super Swarm target packet gets review-only warning', () {
    final result = RemoteWorkerPacket.parse(superSwarmReviewPacketExample);

    expect(
      result.packet!.validationWarnings,
      contains('Super Swarm target packet is review-only.'),
    );
    expect(result.packet!.isSuperSwarmTarget, isTrue);
  });

  test('instructions remain inert display-only data', () {
    final result = RemoteWorkerPacket.parse(manualTaskPacketExample);

    expect(result.packet!.instructions, contains('Do not execute commands'));
    expect(result.packet!.instructions, isA<String>());
  });
}
