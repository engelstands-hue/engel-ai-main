enum EngelDeviceReadiness { ready, offline, stale, unknown }

/// A runtime observation from an authoritative device-health source.
///
/// Registration, pairing, identity, and bootstrap records are not health
/// observations. Callers must leave [usable] null when they only have that
/// metadata. If a source cannot be read or its timestamp cannot be parsed,
/// [sourceValid] must be false.
class EngelDeviceEvidence {
  const EngelDeviceEvidence({
    required this.sourceValid,
    required this.usable,
    required this.observedAtUtc,
    required this.freshness,
  });

  final bool sourceValid;
  final bool? usable;
  final DateTime? observedAtUtc;
  final Duration freshness;
}

class EngelDeviceStatus {
  const EngelDeviceStatus({
    required this.readiness,
    required this.observedAtUtc,
    required this.age,
  });

  final EngelDeviceReadiness readiness;
  final DateTime? observedAtUtc;
  final Duration? age;

  bool get isReady => readiness == EngelDeviceReadiness.ready;

  String get label => switch (readiness) {
    EngelDeviceReadiness.ready => 'Ready',
    EngelDeviceReadiness.offline => 'Needs connection',
    EngelDeviceReadiness.stale => 'Status out of date',
    EngelDeviceReadiness.unknown => 'Not checked',
  };

  String get lastSeenLabel {
    final elapsed = age;
    if (observedAtUtc == null || elapsed == null) {
      return 'Last seen not available';
    }
    if (elapsed.inMinutes < 1) return 'Seen just now';
    if (elapsed.inHours < 1) {
      final minutes = elapsed.inMinutes;
      return 'Seen $minutes ${minutes == 1 ? 'minute' : 'minutes'} ago';
    }
    if (elapsed.inDays < 1) {
      final hours = elapsed.inHours;
      return 'Seen $hours ${hours == 1 ? 'hour' : 'hours'} ago';
    }
    final days = elapsed.inDays;
    return 'Seen $days ${days == 1 ? 'day' : 'days'} ago';
  }
}

EngelDeviceStatus classifyEngelDeviceEvidence(
  EngelDeviceEvidence evidence, {
  DateTime? nowUtc,
}) {
  final observedAt = evidence.observedAtUtc?.toUtc();
  final now = (nowUtc ?? DateTime.now()).toUtc();

  if (!evidence.sourceValid ||
      evidence.usable == null ||
      observedAt == null ||
      evidence.freshness <= Duration.zero) {
    return EngelDeviceStatus(
      readiness: EngelDeviceReadiness.unknown,
      observedAtUtc: observedAt,
      age: null,
    );
  }

  final age = now.difference(observedAt);
  if (age.isNegative) {
    return EngelDeviceStatus(
      readiness: EngelDeviceReadiness.unknown,
      observedAtUtc: observedAt,
      age: null,
    );
  }

  if (age > evidence.freshness) {
    return EngelDeviceStatus(
      readiness: EngelDeviceReadiness.stale,
      observedAtUtc: observedAt,
      age: age,
    );
  }

  return EngelDeviceStatus(
    readiness: evidence.usable!
        ? EngelDeviceReadiness.ready
        : EngelDeviceReadiness.offline,
    observedAtUtc: observedAt,
    age: age,
  );
}

String engelDeviceAggregateLabel(
  String group,
  Iterable<EngelDeviceStatus> statuses,
) {
  final values = statuses.toList(growable: false);
  if (values.isEmpty) return '$group — none checked.';

  int count(EngelDeviceReadiness readiness) =>
      values.where((status) => status.readiness == readiness).length;

  final ready = count(EngelDeviceReadiness.ready);
  final offline = count(EngelDeviceReadiness.offline);
  final stale = count(EngelDeviceReadiness.stale);
  final unknown = count(EngelDeviceReadiness.unknown);
  final parts = <String>[
    '$ready of ${values.length} ready',
    if (offline == 1) '1 needs connection',
    if (offline > 1) '$offline need connection',
    if (stale == 1) '1 status out of date',
    if (stale > 1) '$stale statuses out of date',
    if (unknown > 0) '$unknown not checked',
  ];
  return '$group — ${parts.join(' · ')}.';
}
