import 'package:engel_flutter_main/device_status.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final now = DateTime.utc(2026, 7, 29, 12);
  const defaultFreshness = Duration(minutes: 5);

  EngelDeviceStatus classify({
    bool sourceValid = true,
    bool? usable = true,
    DateTime? observedAtUtc,
    Duration freshness = defaultFreshness,
  }) {
    return classifyEngelDeviceEvidence(
      EngelDeviceEvidence(
        sourceValid: sourceValid,
        usable: usable,
        observedAtUtc: observedAtUtc,
        freshness: freshness,
      ),
      nowUtc: now,
    );
  }

  group('classifyEngelDeviceEvidence', () {
    test('classifies fresh usable authoritative evidence as ready', () {
      final status = classify(
        observedAtUtc: now.subtract(const Duration(minutes: 1)),
      );

      expect(status.readiness, EngelDeviceReadiness.ready);
      expect(status.label, 'Ready');
      expect(status.isReady, isTrue);
    });

    test('classifies fresh unusable authoritative evidence as offline', () {
      final status = classify(
        usable: false,
        observedAtUtc: now.subtract(const Duration(minutes: 1)),
      );

      expect(status.readiness, EngelDeviceReadiness.offline);
      expect(status.label, 'Needs connection');
      expect(status.isReady, isFalse);
    });

    test('keeps the exact freshness boundary fresh', () {
      final ready = classify(observedAtUtc: now.subtract(defaultFreshness));
      final offline = classify(
        usable: false,
        observedAtUtc: now.subtract(defaultFreshness),
      );

      expect(ready.readiness, EngelDeviceReadiness.ready);
      expect(offline.readiness, EngelDeviceReadiness.offline);
    });

    test('classifies evidence beyond the freshness boundary as stale', () {
      final status = classify(
        usable: false,
        observedAtUtc: now.subtract(
          defaultFreshness + const Duration(microseconds: 1),
        ),
      );

      expect(status.readiness, EngelDeviceReadiness.stale);
      expect(status.label, 'Status out of date');
    });

    test('does not trust a future timestamp', () {
      final status = classify(
        observedAtUtc: now.add(const Duration(microseconds: 1)),
      );

      expect(status.readiness, EngelDeviceReadiness.unknown);
      expect(status.label, 'Not checked');
      expect(status.age, isNull);
    });

    test('invalid or malformed source evidence remains unknown', () {
      final status = classify(sourceValid: false, observedAtUtc: now);

      expect(status.readiness, EngelDeviceReadiness.unknown);
    });

    test('missing timestamp remains unknown', () {
      final status = classify();

      expect(status.readiness, EngelDeviceReadiness.unknown);
    });

    test('registration or bootstrap metadata alone cannot become ready', () {
      final status = classify(usable: null, observedAtUtc: now);

      expect(status.readiness, EngelDeviceReadiness.unknown);
      expect(status.isReady, isFalse);
    });

    test('non-positive freshness is invalid', () {
      final zero = classify(observedAtUtc: now, freshness: Duration.zero);
      final negative = classify(
        observedAtUtc: now,
        freshness: const Duration(seconds: -1),
      );

      expect(zero.readiness, EngelDeviceReadiness.unknown);
      expect(negative.readiness, EngelDeviceReadiness.unknown);
    });
  });

  group('engelDeviceAggregateLabel', () {
    EngelDeviceStatus status(EngelDeviceReadiness readiness) {
      return EngelDeviceStatus(
        readiness: readiness,
        observedAtUtc: now,
        age: Duration.zero,
      );
    }

    test('summarizes a ready group with a connection issue', () {
      final label = engelDeviceAggregateLabel('Workers', [
        status(EngelDeviceReadiness.ready),
        status(EngelDeviceReadiness.ready),
        status(EngelDeviceReadiness.ready),
        status(EngelDeviceReadiness.offline),
      ]);

      expect(label, 'Workers — 3 of 4 ready · 1 needs connection.');
    });

    test('summarizes every non-ready state with plural wording', () {
      final label = engelDeviceAggregateLabel('Workers', [
        status(EngelDeviceReadiness.offline),
        status(EngelDeviceReadiness.offline),
        status(EngelDeviceReadiness.stale),
        status(EngelDeviceReadiness.stale),
        status(EngelDeviceReadiness.unknown),
      ]);

      expect(
        label,
        'Workers — 0 of 5 ready · 2 need connection · '
        '2 statuses out of date · 1 not checked.',
      );
    });

    test('reports an empty group without implying health', () {
      expect(
        engelDeviceAggregateLabel('Workers', const []),
        'Workers — none checked.',
      );
    });
  });
}
