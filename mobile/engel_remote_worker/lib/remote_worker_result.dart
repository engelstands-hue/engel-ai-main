import 'dart:convert';

import 'remote_worker_packet.dart';

class RemoteWorkerResult {
  const RemoteWorkerResult._({
    required this.packetId,
    required this.resultType,
    required this.draftText,
    required this.reviewTarget,
    required this.suggestedNextStep,
    required this.generatedAtLocal,
  });

  factory RemoteWorkerResult.fromPacket({
    required RemoteWorkerPacket packet,
    required String draftText,
    String? suggestedNextStep,
    DateTime? generatedAtLocal,
  }) {
    return RemoteWorkerResult._(
      packetId: packet.packetId,
      resultType: packet.taskType.trim().isEmpty
          ? 'manual_draft_result'
          : '${packet.taskType}_draft_result',
      draftText: draftText,
      reviewTarget: packet.hasReviewTarget ? packet.targetDisplayName : null,
      suggestedNextStep:
          suggestedNextStep == null || suggestedNextStep.trim().isEmpty
          ? null
          : suggestedNextStep.trim(),
      generatedAtLocal: generatedAtLocal ?? DateTime.now(),
    );
  }

  static const resultVersion = '1';
  static const workerDevice = 'engel_remote_worker_flutter';
  static const trustLevel = 'untrusted_until_engel_review';

  final String packetId;
  final String resultType;
  final String draftText;
  final String? reviewTarget;
  final String? suggestedNextStep;
  final DateTime generatedAtLocal;

  bool get requiresReview => true;
  bool get safeToAutoApply => false;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'result_version': resultVersion,
      'packet_id': packetId,
      'worker_device': workerDevice,
      'trust_level': trustLevel,
      'result_type': resultType,
      'draft_text': draftText,
      if (reviewTarget != null) 'review_target': reviewTarget,
      if (suggestedNextStep != null) 'suggested_next_step': suggestedNextStep,
      'requires_review': requiresReview,
      'safe_to_auto_apply': safeToAutoApply,
      'generated_at_local': generatedAtLocal.toIso8601String(),
    };
  }

  String toPrettyJson() {
    return const JsonEncoder.withIndent('  ').convert(toJson());
  }
}
