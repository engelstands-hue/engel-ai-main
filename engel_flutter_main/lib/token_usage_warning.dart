import 'package:flutter/material.dart';

/// A usage reading that can be shown to an operator without guessing.
///
/// The Main UI only creates this value when a worker/CT receipt supplies both
/// an explicit used-token count and an explicit provider limit.  In
/// particular, a per-request `max_tokens` value or a model context window is
/// never treated as an account quota.
class TokenUsageSnapshot {
  const TokenUsageSnapshot({
    required this.usedTokens,
    required this.tokenLimit,
    required this.providerName,
    this.period = '',
    this.source = '',
  });

  final int usedTokens;
  final int tokenLimit;
  final String providerName;
  final String period;
  final String source;

  int get percent =>
      tokenUsagePercent(usedTokens: usedTokens, tokenLimit: tokenLimit);

  Map<String, Object?> toJson() => {
    'schema': 'engel_token_usage_v1',
    'used_tokens': usedTokens,
    'token_limit': tokenLimit,
    'provider': providerName,
    if (period.isNotEmpty) 'period': period,
    if (source.isNotEmpty) 'source': source,
  };

  /// Reads the canonical usage object from a Main worker response.
  ///
  /// This deliberately requires the producer's trust marker (or the
  /// canonical schema plus `trusted: true`).  Missing, malformed, or
  /// untrusted usage is represented by `null`, so the UI cannot invent a
  /// quota from `max_tokens`, context length, or text in an assistant reply.
  static TokenUsageSnapshot? fromResponse(Map<String, dynamic>? response) {
    if (response == null) return null;

    final candidates =
        <
          ({
            Map<dynamic, dynamic> value,
            Map<dynamic, dynamic>? parent,
            String source,
          })
        >[];

    void add(Object? raw, String source, [Map<dynamic, dynamic>? parent]) {
      if (raw is Map) {
        candidates.add((value: raw, parent: parent, source: source));
      }
    }

    final receipt = response['receipt'];
    final receiptMap = receipt is Map ? receipt : null;
    add(response['token_usage'], 'response.token_usage', response);
    add(response['usage'], 'response.usage', response);
    add(receiptMap?['token_usage'], 'receipt.token_usage', receiptMap);
    add(receiptMap?['usage'], 'receipt.usage', receiptMap);
    // A canonical object may itself be the response (useful for local test
    // runners and future API envelopes).
    add(response, 'response');
    if (receiptMap != null) add(receiptMap, 'receipt');

    for (final candidate in candidates) {
      final map = candidate.value;
      final parent = candidate.parent;
      if (!_isTrustedUsageMap(map, parent)) continue;

      final used = _readNonNegativeInt(map, const [
        'used_tokens',
        'tokens_used',
        'total_tokens',
      ]);
      final limit =
          _readPositiveInt(map, const [
            'token_limit',
            'limit_tokens',
            'usage_limit',
            'quota_limit',
          ]) ??
          (parent == null
              ? null
              : _readPositiveInt(parent, const [
                  'token_limit',
                  'limit_tokens',
                  'usage_limit',
                  'quota_limit',
                ]));
      if (used == null || limit == null) continue;

      final provider = _safeLabel(
        map['provider_name'] ??
            map['provider'] ??
            parent?['provider_name'] ??
            parent?['provider'],
      );
      final period = _safeLabel(map['period'] ?? parent?['period']);
      final source =
          _safeLabel(map['source'] ?? parent?['usage_source']) ??
          candidate.source;
      return TokenUsageSnapshot(
        usedTokens: used,
        tokenLimit: limit,
        providerName: provider ?? 'Current provider',
        period: period ?? '',
        source: source,
      );
    }
    return null;
  }

  static bool _isTrustedUsageMap(
    Map<dynamic, dynamic> map,
    Map<dynamic, dynamic>? parent,
  ) {
    final schema = map['schema']?.toString().trim();
    final trusted = map['trusted'] == true || map['usage_trusted'] == true;
    final parentTrusted = parent?['usage_trusted'] == true;
    return (schema == 'engel_token_usage_v1' && trusted) ||
        parentTrusted ||
        (trusted && schema == null);
  }

  static int? _readNonNegativeInt(
    Map<dynamic, dynamic> map,
    List<String> keys,
  ) {
    for (final key in keys) {
      final value = _asWholeInt(map[key]);
      if (value != null && value >= 0) return value;
    }
    return null;
  }

  static int? _readPositiveInt(Map<dynamic, dynamic> map, List<String> keys) {
    for (final key in keys) {
      final value = _asWholeInt(map[key]);
      if (value != null && value > 0) return value;
    }
    return null;
  }

  static int? _asWholeInt(Object? value) {
    if (value is bool) return null;
    if (value is int) return value;
    if (value is num && value.isFinite && value == value.round()) {
      return value.toInt();
    }
    if (value is String && RegExp(r'^\d+$').hasMatch(value.trim())) {
      return int.tryParse(value.trim());
    }
    return null;
  }

  static String? _safeLabel(Object? value) {
    if (value == null) return null;
    final text = value.toString().trim();
    if (text.isEmpty) return null;
    // Provider labels/periods are display metadata, never paths or receipts.
    final clipped = text.length > 80 ? text.substring(0, 80) : text;
    return clipped.replaceAll(RegExp(r'[\r\n\t]'), ' ');
  }
}

enum TokenUsageWarningLevel { none, approachingLimit, limitReached }

TokenUsageWarningLevel tokenUsageWarningLevel({
  required int usedTokens,
  required int tokenLimit,
}) {
  if (tokenLimit <= 0 || usedTokens < 0) return TokenUsageWarningLevel.none;
  final ratio = usedTokens / tokenLimit;
  if (ratio >= 1) return TokenUsageWarningLevel.limitReached;
  if (ratio >= .75) return TokenUsageWarningLevel.approachingLimit;
  return TokenUsageWarningLevel.none;
}

int tokenUsagePercent({required int usedTokens, required int tokenLimit}) {
  if (tokenLimit <= 0 || usedTokens < 0) return 0;
  final percent = (usedTokens / tokenLimit * 100).round();
  return percent.clamp(0, 100);
}

/// An honest, provider-neutral usage notice. It renders only when both usage
/// and limit are supplied by a trusted local status source; it never estimates
/// or fabricates provider usage.
class TokenUsageWarning extends StatelessWidget {
  const TokenUsageWarning({
    super.key,
    required this.usedTokens,
    required this.tokenLimit,
    required this.providerName,
  });

  final int usedTokens;
  final int tokenLimit;
  final String providerName;

  factory TokenUsageWarning.fromSnapshot(
    TokenUsageSnapshot snapshot, {
    Key? key,
  }) {
    return TokenUsageWarning(
      key: key,
      usedTokens: snapshot.usedTokens,
      tokenLimit: snapshot.tokenLimit,
      providerName: snapshot.providerName,
    );
  }

  @override
  Widget build(BuildContext context) {
    final level = tokenUsageWarningLevel(
      usedTokens: usedTokens,
      tokenLimit: tokenLimit,
    );
    if (level == TokenUsageWarningLevel.none) return const SizedBox.shrink();
    final reached = level == TokenUsageWarningLevel.limitReached;
    final percent = tokenUsagePercent(
      usedTokens: usedTokens,
      tokenLimit: tokenLimit,
    );
    final message = reached
        ? '$providerName token limit reached ($percent%). Your unfinished work is saved. To continue with this provider, add API billing or upgrade your plan.'
        : '$providerName token usage is $percent% (75% warning). Save your work soon; add API billing or upgrade your plan before the limit is reached.';
    return Card(
      key: const Key('engel-token-usage-warning'),
      color: reached ? const Color(0xff4a1f25) : const Color(0xff4a3d1f),
      child: ListTile(
        leading: Icon(
          reached ? Icons.block : Icons.warning_amber,
          color: reached ? Colors.redAccent : Colors.amber,
        ),
        title: Text(reached ? 'Token limit reached' : 'Token usage warning'),
        subtitle: Text(message),
      ),
    );
  }
}
