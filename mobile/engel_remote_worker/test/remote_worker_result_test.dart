import 'dart:convert';

import 'package:engel_remote_worker/remote_worker_packet.dart';
import 'package:engel_remote_worker/remote_worker_result.dart';
import 'package:flutter_test/flutter_test.dart';

import 'remote_worker_packet_test.dart'
    show engelReviewPacketExample, manualTaskPacketExample;

void main() {
  RemoteWorkerResult buildResult({String? nextStep, String? packetJson}) {
    final packet = RemoteWorkerPacket.parse(
      packetJson ?? engelReviewPacketExample,
    ).packet!;
    return RemoteWorkerResult.fromPacket(
      packet: packet,
      draftText: 'Draft observation for review.',
      suggestedNextStep: nextStep,
      generatedAtLocal: DateTime.utc(2026, 5, 16, 12),
    );
  }

  test('result JSON includes packet_id', () {
    final json = buildResult().toJson();

    expect(json['packet_id'], 'engel-review-001');
  });

  test('result JSON includes worker_device', () {
    final json = buildResult().toJson();

    expect(json['worker_device'], 'engel_remote_worker_flutter');
  });

  test('result JSON has untrusted trust level', () {
    final json = buildResult().toJson();

    expect(json['trust_level'], 'untrusted_until_engel_review');
  });

  test('result JSON requires review', () {
    final json = buildResult().toJson();

    expect(json['requires_review'], isTrue);
  });

  test('result JSON has safe_to_auto_apply false', () {
    final json = buildResult().toJson();

    expect(json['safe_to_auto_apply'], isFalse);
  });

  test('safe_to_auto_apply cannot be generated true', () {
    final decoded = jsonDecode(buildResult().toPrettyJson());

    expect(decoded['safe_to_auto_apply'], isFalse);
  });

  test('suggested next step is included when provided', () {
    final json = buildResult(nextStep: 'Queue for human review.').toJson();

    expect(json['suggested_next_step'], 'Queue for human review.');
  });

  test('empty or unknown review target handled safely', () {
    final result = buildResult(packetJson: manualTaskPacketExample).toJson();

    expect(result.containsKey('review_target'), isFalse);
    expect(result['safe_to_auto_apply'], isFalse);
  });
}
