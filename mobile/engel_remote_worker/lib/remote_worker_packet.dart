import 'dart:convert';

const requiredBlockedActions = <String>{
  'execute_commands',
  'write_trusted_memory',
  'mutate_queue',
  'mutate_routes',
  'mutate_source',
  'control_engel',
  'auto_apply_fixes',
};

class RemoteWorkerPacketParseResult {
  const RemoteWorkerPacketParseResult._({this.packet, this.error});

  const RemoteWorkerPacketParseResult.success(RemoteWorkerPacket packet)
    : this._(packet: packet);

  const RemoteWorkerPacketParseResult.failure(String error)
    : this._(error: error);

  final RemoteWorkerPacket? packet;
  final String? error;

  bool get isSuccess => packet != null;
}

class RemoteWorkerPacket {
  const RemoteWorkerPacket({
    required this.packetVersion,
    required this.packetId,
    required this.createdBy,
    required this.trustLevel,
    required this.taskType,
    required this.title,
    required this.instructions,
    required this.allowedOutputs,
    required this.blockedActions,
    required this.raw,
    this.targetSystem,
    this.reviewMode,
    this.sourceSummary,
    this.verifierContext,
  });

  factory RemoteWorkerPacket.fromMap(Map<String, dynamic> json) {
    return RemoteWorkerPacket(
      packetVersion: _stringValue(json['packet_version']),
      packetId: _stringValue(json['packet_id']),
      createdBy: _stringValue(json['created_by']),
      trustLevel: _stringValue(json['trust_level']),
      taskType: _stringValue(json['task_type']),
      title: _stringValue(json['title']),
      instructions: _stringValue(json['instructions']),
      allowedOutputs: _stringList(json['allowed_outputs']),
      blockedActions: _stringList(json['blocked_actions']),
      targetSystem: _nullableStringValue(json['target_system']),
      reviewMode: _nullableStringValue(json['review_mode']),
      sourceSummary: _nullableStringValue(json['source_summary']),
      verifierContext: json['verifier_context'],
      raw: Map<String, dynamic>.from(json),
    );
  }

  static RemoteWorkerPacketParseResult parse(String input) {
    try {
      final decoded = jsonDecode(input);
      if (decoded is! Map<String, dynamic>) {
        return const RemoteWorkerPacketParseResult.failure(
          'Packet JSON must be an object.',
        );
      }
      return RemoteWorkerPacketParseResult.success(
        RemoteWorkerPacket.fromMap(decoded),
      );
    } on FormatException catch (error) {
      return RemoteWorkerPacketParseResult.failure(
        'Invalid JSON: ${error.message}',
      );
    } on Object catch (error) {
      return RemoteWorkerPacketParseResult.failure(
        'Packet could not be parsed safely: $error',
      );
    }
  }

  final String packetVersion;
  final String packetId;
  final String createdBy;
  final String trustLevel;
  final String taskType;
  final String title;
  final String instructions;
  final List<String> allowedOutputs;
  final List<String> blockedActions;
  final String? targetSystem;
  final String? reviewMode;
  final String? sourceSummary;
  final dynamic verifierContext;
  final Map<String, dynamic> raw;

  bool get hasReviewTarget =>
      targetSystem != null && targetSystem!.trim().isNotEmpty;

  bool get isEngelTarget => targetSystem?.trim().toLowerCase() == 'engel';

  bool get isSuperSwarmTarget =>
      targetSystem?.trim().toLowerCase() == 'super swarm';

  bool get hasAllRequiredBlockedActions =>
      requiredBlockedActions.every(blockedActions.contains);

  String get targetDisplayName {
    if (isEngelTarget) {
      return 'Engel';
    }
    if (isSuperSwarmTarget) {
      return 'Super Swarm';
    }
    if (hasReviewTarget) {
      return targetSystem!.trim();
    }
    return 'Manual Worker Packet';
  }

  String get verifierContextSummary {
    final context = verifierContext;
    if (context == null) {
      return '';
    }
    if (context is String) {
      return context;
    }
    return const JsonEncoder.withIndent('  ').convert(context);
  }

  List<String> get validationWarnings {
    final warnings = <String>[];

    if (packetId.trim().isEmpty) {
      warnings.add('Missing packet_id.');
    }
    if (title.trim().isEmpty) {
      warnings.add('Missing title.');
    }
    if (trustLevel.trim().isEmpty) {
      warnings.add('Missing trust_level.');
    }
    if (!raw.containsKey('blocked_actions')) {
      warnings.add('Missing blocked_actions.');
    } else if (raw['blocked_actions'] is! List) {
      warnings.add('blocked_actions must be a list.');
    }

    for (final action in requiredBlockedActions) {
      if (!blockedActions.contains(action)) {
        warnings.add('Missing required blocked action: $action.');
      }
    }

    if (isEngelTarget) {
      warnings.add('Engel target packet is review-only.');
    }
    if (isSuperSwarmTarget) {
      warnings.add('Super Swarm target packet is review-only.');
    }
    if (!raw.containsKey('allowed_outputs') || allowedOutputs.isEmpty) {
      warnings.add('Missing or empty allowed_outputs.');
    }
    if (instructions.trim().isEmpty) {
      warnings.add('Missing instructions.');
    }

    return warnings;
  }

  bool get isValidForManualReview =>
      packetId.trim().isNotEmpty &&
      title.trim().isNotEmpty &&
      trustLevel.trim().isNotEmpty &&
      raw['blocked_actions'] is List &&
      hasAllRequiredBlockedActions;
}

String _stringValue(dynamic value) {
  if (value == null) {
    return '';
  }
  return value.toString();
}

String? _nullableStringValue(dynamic value) {
  if (value == null) {
    return null;
  }
  final text = value.toString();
  return text.trim().isEmpty ? null : text;
}

List<String> _stringList(dynamic value) {
  if (value is! List) {
    return const [];
  }
  return value.map((item) => item.toString()).toList(growable: false);
}
