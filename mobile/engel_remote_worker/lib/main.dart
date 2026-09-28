// Engel Remote Worker — Android tool window (HUD edition).
//
// Intentionally minimal in FUNCTION. This is a TOOL, not a feature app:
//   • A status header identifying THIS phone (device label + worker_id).
//   • Live telemetry (link quality, poll activity, battery, uptime) —
//     every gauge is driven by real data, never decorative fakes.
//   • A small panel showing which agent from the Meeting Room is currently
//     assigned (last seen in `/worker/next-assignment`).
//   • A scrollable monospace transcript of what the assigned agent has
//     written most recently.
//
// Networking goes through LanPairingClient (see lan_pairing_client.dart).
// The phone:
//   1. reads worker_identity.json (newest valid file wins),
//   2. self-detects its hardware model (hardware is the authority),
//   3. auto-discovers Engel's LAN receiver broadcast over WiFi,
//   4. auto-pairs (a successful pair persists the connection config),
//   5. polls /worker/next-assignment after pairing,
//   6. returns bounded untrusted draft results via /worker/return-result.
//
// Theme: Engel HUD — near-black bg, neon green/cyan/purple, monospace,
// cut-corner panels, corner brackets, animated grid + scanline.

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;

import 'package:battery_plus/battery_plus.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import 'desk_phone_sandbox.dart';
import 'lan_pairing_client.dart';
import 'new_tech_theme.dart';
import 'worker_avatar.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  unawaited(WakelockPlus.enable());
  runApp(const EngelRemoteWorkerApp());
}

// ─── Palette (Engel HUD) ─────────────────────────────────────────────────────
class _Palette {
  static const bg = Color(0xFF07070E);
  static const card = Color(0xFF0D0D18);
  static const card2 = Color(0xFF10101F);
  static const border = Color(0xFF1C1C32);
  static const border2 = Color(0xFF2A2A48);
  static const text = Color(0xFFC8C8E8);
  static const dim = Color(0xFF5A5A7A);
  static const green = Color(0xFF00E87A);
  static const cyan = Color(0xFF00D4FF);
  static const amber = Color(0xFFFFAA00);
  static const red = Color(0xFFFF4455);
  static const purple = Color(0xFFAA77FF);
}

const _mono = TextStyle(
  fontFamily: 'monospace',
  fontFamilyFallback: ['Consolas', 'Roboto Mono', 'Courier New'],
);

// ─── Worker identity (device-side JSON) ─────────────────────────────────────
class WorkerIdentity {
  const WorkerIdentity({
    required this.workerId,
    required this.workerName,
    required this.phoneModel,
    this.agentId = '',
    this.agentName = '',
    this.brainId = '',
    this.brainLabel = '',
    this.brainLane = '',
    this.fromDefault = false,
  });

  final String workerId;
  final String workerName;
  final String phoneModel;
  final String agentId;
  final String agentName;
  final String brainId;
  final String brainLabel;
  final String brainLane;

  /// True when no valid provisioned identity was found and the app fell back
  /// to the built-in default (which collides with the real alpha phone).
  final bool fromDefault;

  static final idPattern = RegExp(r'^[a-z][a-z0-9_]{2,40}$');

  /// Dedicated Agent + Brain defaults when identity JSON omits them.
  /// Brain is a PC-side lane identity shown on HUD — not on-device model runtime.
  static const Map<String, Map<String, String>> _agentBrainDefaults =
      <String, Map<String, String>>{
    'android_worker_alpha': <String, String>{
      'agent_id': 'android_phone_alpha_agent',
      'agent_name': 'Android Phone Alpha Agent',
      'brain_id': 'brain_alpha_research_companion',
      'brain_label': 'Research Companion SLM',
      'brain_lane': 'companion_3b_research_note',
    },
    'android_worker_beta': <String, String>{
      'agent_id': 'android_phone_beta_agent',
      'agent_name': 'Android Phone Beta Agent',
      'brain_id': 'brain_beta_json_structurer',
      'brain_label': 'JSON Structurer SLM',
      'brain_lane': 'companion_3b_json_draft',
    },
    'android_worker_gamma': <String, String>{
      'agent_id': 'android_phone_gamma_agent',
      'agent_name': 'Android Phone Gamma Agent',
      'brain_id': 'brain_gamma_local_compute',
      'brain_label': 'Local Compute / Report SLM',
      'brain_lane': 'companion_3b_report_format',
    },
  };

  static Map<String, String> defaultsFor(String workerId) {
    return _agentBrainDefaults[workerId] ??
        <String, String>{
          'agent_id': '${workerId}_agent',
          'agent_name': 'Android Phone Agent',
          'brain_id': '${workerId}_brain',
          'brain_label': 'Dedicated Brain',
          'brain_lane': 'companion_lane',
        };
  }

  static const _path =
      '/storage/emulated/0/Android/data/com.example.engel_remote_worker/files/worker_identity.json';
  static const _internalPath =
      '/data/user/0/com.example.engel_remote_worker/files/worker_identity.json';
  // Android 13+ blocks adb push into Android/data, so provisioning from the
  // Engel PC also works via the world-writable Download folder.
  static const _downloadPath =
      '/storage/emulated/0/Download/EngelRemoteWorker/worker_identity.json';

  // The NEWEST valid candidate wins, not a fixed path priority: the app
  // auto-saves to the internal path (model detection, UI adoption), and an
  // internal-first order would permanently shadow the Download folder — the
  // documented Android 13+ re-provisioning channel. Newest-wins means a
  // freshly pushed provisioning file always takes effect on next launch.
  static WorkerIdentity load() {
    WorkerIdentity? best;
    DateTime? bestModified;
    for (final candidate in [_internalPath, _path, _downloadPath]) {
      try {
        final file = File(candidate);
        if (!file.existsSync()) continue;
        final raw = jsonDecode(file.readAsStringSync());
        if (raw is! Map) continue;
        final id = (raw['worker_id'] as String?) ?? '';
        if (!idPattern.hasMatch(id)) continue; // malformed file: keep looking
        final modified = file.lastModifiedSync();
        if (bestModified != null && !modified.isAfter(bestModified)) continue;
        bestModified = modified;
        final defaults = defaultsFor(id);
        best = WorkerIdentity(
          workerId: id,
          workerName: (raw['worker_name'] as String?) ?? 'Android Worker',
          phoneModel: (raw['phone_model'] as String?) ?? 'unknown device',
          agentId: ((raw['agent_id'] as String?)?.trim().isNotEmpty == true)
              ? raw['agent_id'] as String
              : defaults['agent_id']!,
          agentName: ((raw['agent_name'] as String?)?.trim().isNotEmpty == true)
              ? raw['agent_name'] as String
              : defaults['agent_name']!,
          brainId: ((raw['brain_id'] as String?)?.trim().isNotEmpty == true)
              ? raw['brain_id'] as String
              : defaults['brain_id']!,
          brainLabel:
              ((raw['brain_label'] as String?)?.trim().isNotEmpty == true)
                  ? raw['brain_label'] as String
                  : defaults['brain_label']!,
          brainLane: ((raw['brain_lane'] as String?)?.trim().isNotEmpty == true)
              ? raw['brain_lane'] as String
              : defaults['brain_lane']!,
        );
      } catch (_) {
        continue; // unreadable candidate: keep looking
      }
    }
    if (best != null) return best;
    const defaultId = 'android_worker_alpha';
    final defaults = defaultsFor(defaultId);
    return WorkerIdentity(
      workerId: defaultId,
      workerName: 'Android Worker (default)',
      phoneModel: 'unknown device',
      agentId: defaults['agent_id']!,
      agentName: defaults['agent_name']!,
      brainId: defaults['brain_id']!,
      brainLabel: defaults['brain_label']!,
      brainLane: defaults['brain_lane']!,
      fromDefault: true,
    );
  }

  // Persist an identity chosen in the app UI so it survives restarts and
  // upgrades. Internal storage is always writable by the app itself.
  void save() {
    try {
      final file = File(_internalPath);
      file.parent.createSync(recursive: true);
      file.writeAsStringSync(
        jsonEncode({
          'worker_id': workerId,
          'worker_name': workerName,
          'phone_model': phoneModel,
          'agent_id': agentId,
          'agent_name': agentName,
          'brain_id': brainId,
          'brain_label': brainLabel,
          'brain_lane': brainLane,
          'discord_on_phone': false,
          'controls_engel': false,
          'model_runtime': false,
        }),
      );
    } catch (_) {
      // best effort; identity still applies for this session
    }
  }
}

class WorkerConnectionConfig {
  const WorkerConnectionConfig({
    required this.host,
    required this.port,
    required this.pairingCode,
    required this.autoPair,
  });

  final String host;
  final int port;
  final String pairingCode;
  final bool autoPair;

  /// Canonical Engel LAN pairing receiver on the ROG (engel-ai-rs).
  /// Phones must not default to loopback — that only worked with USB adb-reverse.
  static const canonicalLanHost = '192.0.2.40';
  static const canonicalLanPort = 8765;

  static const _path =
      '/storage/emulated/0/Android/data/com.example.engel_remote_worker/files/worker_connection.json';
  static const _internalPath =
      '/data/user/0/com.example.engel_remote_worker/files/worker_connection.json';
  static const _downloadPath =
      '/storage/emulated/0/Download/EngelRemoteWorker/worker_connection.json';

  static bool isLoopbackHost(String host) {
    final h = host.trim().toLowerCase();
    return h == '127.0.0.1' ||
        h == 'localhost' ||
        h == '::1' ||
        h == '0.0.0.0';
  }

  /// Rewrite USB-era loopback hosts to the Engel LAN receiver.
  static String normalizeHost(String host) {
    final trimmed = host.trim();
    if (trimmed.isEmpty || isLoopbackHost(trimmed)) {
      return canonicalLanHost;
    }
    return trimmed;
  }

  static int normalizePort(int port) {
    if (port <= 0 || port > 65535) return canonicalLanPort;
    return port;
  }

  static WorkerConnectionConfig? load() {
    try {
      File? file;
      for (final candidate in [_path, _internalPath, _downloadPath]) {
        if (File(candidate).existsSync()) {
          file = File(candidate);
          break;
        }
      }
      if (file == null) return null;
      final raw = jsonDecode(file.readAsStringSync());
      if (raw is! Map) return null;
      final map = Map<String, dynamic>.from(raw);
      final hostRaw = (map['host'] as String?)?.trim() ?? '';
      final code = (map['pairing_code'] as String?)?.trim() ?? '';
      if (hostRaw.isEmpty || code.isEmpty) return null;
      final portRaw = map['port'];
      final portParsed = portRaw is int
          ? portRaw
          : int.tryParse('$portRaw') ?? canonicalLanPort;
      final host = normalizeHost(hostRaw);
      final port = normalizePort(portParsed);
      final config = WorkerConnectionConfig(
        host: host,
        port: port,
        pairingCode: code,
        autoPair: map['auto_pair'] != false,
      );
      // Persist migration so UI and next launch stop showing 127.0.0.1.
      if (host != hostRaw || port != portParsed) {
        config.save();
      }
      return config;
    } catch (_) {
      return null;
    }
  }

  // Persist the connection that actually paired so this phone re-pairs by
  // itself on every later launch. Without this, a phone with no provisioned
  // config (gamma) stays NOT PAIRED after any app restart until an operator
  // retypes the host and code - there is no PC-side discovery broadcaster.
  void save() {
    try {
      final file = File(_internalPath);
      file.parent.createSync(recursive: true);
      final host = normalizeHost(this.host);
      final port = normalizePort(this.port);
      final payload = jsonEncode({
        'host': host,
        'port': port,
        'pairing_code': pairingCode,
        'auto_pair': autoPair,
      });
      file.writeAsStringSync(payload);
      // Also rewrite external Android/data copy if present (older provision path).
      try {
        final external = File(_path);
        if (external.existsSync() || external.parent.existsSync()) {
          external.parent.createSync(recursive: true);
          external.writeAsStringSync(payload);
        }
      } catch (_) {}
    } catch (_) {
      // best effort; connection still applies for this session
    }
  }
}

// ─── App shell ───────────────────────────────────────────────────────────────
class EngelRemoteWorkerApp extends StatelessWidget {
  const EngelRemoteWorkerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Engel Worker',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: _Palette.bg,
        colorScheme: const ColorScheme.dark(
          surface: _Palette.bg,
          primary: _Palette.green,
          secondary: _Palette.purple,
        ),
        textTheme: const TextTheme(
          bodyMedium: TextStyle(color: _Palette.text),
        ).apply(fontFamily: 'monospace'),
      ),
      home: const WorkerHomePage(),
    );
  }
}

// ─── Home page ───────────────────────────────────────────────────────────────
class WorkerHomePage extends StatefulWidget {
  const WorkerHomePage({super.key});

  @override
  State<WorkerHomePage> createState() => _WorkerHomePageState();
}

class _WorkerHomePageState extends State<WorkerHomePage>
    with WidgetsBindingObserver, TickerProviderStateMixin {
  late WorkerIdentity _identity;
  late LanPairingClient _client;
  final _hostCtrl = TextEditingController();
  final _portCtrl = TextEditingController(text: '8765');
  final _codeCtrl = TextEditingController();
  final _workerIdCtrl = TextEditingController();
  final _transcriptCtrl = ScrollController();
  Timer? _autoPollTimer;
  RawDatagramSocket? _discoverySocket;
  bool _autoModeEnabled = false;
  bool _polling = false;
  String _lastDiscoveryCode = '';

  String _connState = 'NOT PAIRED';
  Color _connColor = _Palette.amber;
  String _currentAgent = '';
  String _currentBrain = '';
  String _currentTitle = '';
  String _lastAssignmentId = '';
  bool _discordPipeJob = false;
  final List<_Message> _messages = [];

  // ── Live telemetry (real data only — gauges never show fabricated values).
  late final AnimationController _ambient; // slow loop: grid scan + radar
  late final AnimationController _pulse; // fast breathe: glows + dots
  final List<double> _pollHistory = []; // 1.0 = ok poll/pair, 0.0 = failure
  static const _pollHistoryMax = 48;
  int _assignmentsReceived = 0;
  int _resultsReturned = 0;
  final Battery _battery = Battery();
  StreamSubscription<BatteryState>? _batterySub;
  Timer? _batteryTimer;
  int _batteryLevel = -1; // -1 = not read yet
  BatteryState _batteryState = BatteryState.unknown;
  final DateTime _sessionStart = DateTime.now();

  /// Avatar face lightness: 0 = darkest horror · 1 = readable face.
  /// Default 0.62 so first open is usable; user can darken.
  static const _faceLightPrefKey = 'avatar_face_light';
  static const _faceLightDefault = 0.62;
  double _faceLight = _faceLightDefault;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_loadFaceLightPref());
    _ambient = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 8),
    )..repeat();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
    _identity = WorkerIdentity.load();
    unawaited(DeskPhoneSandbox.ensureForWorker(_identity.workerId));
    _workerIdCtrl.text = _identity.workerId;
    _currentAgent = _identity.agentName;
    _currentBrain = _identity.brainLabel;
    _client = LanPairingClient(
      workerId: _identity.workerId,
      workerName: _identity.workerName,
      phoneModel: _identity.phoneModel,
    );
    SystemChrome.setSystemUIOverlayStyle(SystemUiOverlayStyle.light);
    unawaited(WakelockPlus.enable());
    _push(
      'SYSTEM',
      'Engel Remote Worker started. Identity: ${_identity.workerId} · '
      'Agent: ${_identity.agentName} · Brain: ${_identity.brainLabel}',
      _Palette.dim,
    );
    if (_identity.fromDefault) {
      _push(
        'SYSTEM',
        'IDENTITY NOT PROVISIONED: running on the built-in default '
        '(${_identity.workerId}), which collides with the real alpha phone. '
        'Type this device\'s worker id below and Test Pairing to fix.',
        _Palette.amber,
      );
    }
    final config = WorkerConnectionConfig.load();
    if (config != null) {
      _hostCtrl.text = config.host;
      _portCtrl.text = config.port.toString();
      _codeCtrl.text = config.pairingCode;
      _push(
        'SYSTEM',
        'Loaded Engel PC connection config '
        '(${config.host}:${config.port}).',
        _Palette.dim,
      );
      if (config.autoPair) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) unawaited(_pair());
        });
      }
    } else {
      // No saved config: default to Engel LAN receiver, not USB loopback.
      _hostCtrl.text = WorkerConnectionConfig.canonicalLanHost;
      _portCtrl.text = WorkerConnectionConfig.canonicalLanPort.toString();
      _push(
        'SYSTEM',
        'No saved PC host — defaulting to '
        '${WorkerConnectionConfig.canonicalLanHost}:'
        '${WorkerConnectionConfig.canonicalLanPort}.',
        _Palette.dim,
      );
    }
    unawaited(_resolvePhoneModel());
    unawaited(_startDiscoveryListener());
    unawaited(_refreshBattery());
    _batteryTimer = Timer.periodic(
      const Duration(seconds: 30),
      (_) => unawaited(_refreshBattery()),
    );
    _batterySub = _battery.onBatteryStateChanged.listen((_) {
      unawaited(_refreshBattery());
    });
  }

  Future<void> _loadFaceLightPref() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getDouble(_faceLightPrefKey);
      if (!mounted) return;
      setState(() {
        _faceLight = (saved ?? _faceLightDefault).clamp(0.0, 1.0);
      });
    } catch (_) {
      // Keep default.
    }
  }

  Future<void> _persistFaceLight(double value) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setDouble(_faceLightPrefKey, value.clamp(0.0, 1.0));
    } catch (_) {
      // best effort
    }
  }

  // The hardware is the authority for the device-info line, not the
  // provisioned JSON: identity files can be missing (UI-adopted identities
  // never carried a model, so gamma showed "unknown device") or copied from
  // another phone and lie. Detected model is persisted so pairing and
  // capability reports carry real device info too.
  Future<void> _resolvePhoneModel() async {
    final detected = await _detectPhoneModel();
    if (detected.isEmpty || detected == _identity.phoneModel) return;
    if (!mounted) return;
    setState(() {
      _identity = WorkerIdentity(
        workerId: _identity.workerId,
        workerName: _identity.workerName,
        phoneModel: detected,
        agentId: _identity.agentId,
        agentName: _identity.agentName,
        brainId: _identity.brainId,
        brainLabel: _identity.brainLabel,
        brainLane: _identity.brainLane,
        fromDefault: _identity.fromDefault,
      );
    });
    // Never persist the built-in default identity: saving it would make the
    // next load() treat android_worker_alpha as provisioned on this phone and
    // silence the not-provisioned warning. The detected model still applies
    // in-session and is saved once a real worker id is adopted.
    if (!_identity.fromDefault) {
      _identity.save();
    }
    _client = LanPairingClient(
      workerId: _identity.workerId,
      workerName: _identity.workerName,
      phoneModel: detected,
    );
  }

  static Future<String> _detectPhoneModel() async {
    if (!Platform.isAndroid) return '';
    try {
      final info = await DeviceInfoPlugin().androidInfo;
      final manufacturer = info.manufacturer.trim();
      final brand = manufacturer.isEmpty
          ? ''
          : manufacturer[0].toUpperCase() + manufacturer.substring(1);
      final model = info.model.trim();
      final name = model.toLowerCase().startsWith(manufacturer.toLowerCase())
          ? model
          : '$brand $model'.trim();
      if (name.isEmpty) return '';
      final release = info.version.release.trim();
      return release.isEmpty ? name : '$name / Android $release';
    } catch (_) {
      return '';
    }
  }

  Future<void> _refreshBattery() async {
    try {
      final level = await _battery.batteryLevel;
      final state = await _battery.batteryState;
      if (!mounted) return;
      setState(() {
        _batteryLevel = level;
        _batteryState = state;
      });
    } catch (_) {
      // battery telemetry is optional; the gauge shows "--" when unavailable
    }
  }

  void _recordPoll(bool ok) {
    if (!mounted) return;
    setState(() {
      _pollHistory.add(ok ? 1.0 : 0.0);
      if (_pollHistory.length > _pollHistoryMax) _pollHistory.removeAt(0);
    });
  }

  // Link quality: success ratio over the most recent polls (real data).
  double get _linkQuality {
    if (_pollHistory.isEmpty) return _connState == 'PAIRED' ? 1.0 : 0.0;
    final window = _pollHistory.length < 12
        ? _pollHistory
        : _pollHistory.sublist(_pollHistory.length - 12);
    final sum = window.fold<double>(0, (a, b) => a + b);
    return sum / window.length;
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _hostCtrl.dispose();
    _portCtrl.dispose();
    _codeCtrl.dispose();
    _workerIdCtrl.dispose();
    _transcriptCtrl.dispose();
    _autoPollTimer?.cancel();
    _discoverySocket?.close();
    _batteryTimer?.cancel();
    _batterySub?.cancel();
    _ambient.dispose();
    _pulse.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) return;
    unawaited(WakelockPlus.enable());
    if (_discoverySocket == null) {
      unawaited(_startDiscoveryListener());
    }
    if (_hostCtrl.text.trim().isNotEmpty && _codeCtrl.text.trim().isNotEmpty) {
      unawaited(_pair());
    }
    if (_autoModeEnabled) {
      unawaited(_pollOnce());
    }
    unawaited(_refreshBattery());
    _push(
      'Wake Guard',
      'Resumed Engel worker: wakelock refreshed and WiFi pairing checked.',
      _Palette.green,
    );
  }

  Future<void> _startDiscoveryListener() async {
    try {
      final socket = await RawDatagramSocket.bind(
        InternetAddress.anyIPv4,
        8766,
        reuseAddress: true,
      );
      _discoverySocket = socket;
      socket.broadcastEnabled = true;
      socket.listen((event) {
        if (event != RawSocketEvent.read) return;
        final datagram = socket.receive();
        if (datagram == null) return;
        _handleDiscoveryDatagram(datagram);
      });
      _push('SYSTEM', 'Listening for Engel LAN discovery.', _Palette.dim);
    } catch (error) {
      if (mounted) {
        _push('SYSTEM', 'LAN discovery unavailable: $error', _Palette.amber);
      }
    }
  }

  void _handleDiscoveryDatagram(Datagram datagram) {
    try {
      final decoded = jsonDecode(utf8.decode(datagram.data));
      if (decoded is! Map<String, Object?> || decoded['engel'] != 1) return;
      final code = decoded['pairing_code']?.toString().trim() ?? '';
      final portValue = decoded['port'];
      final port = portValue is int
          ? portValue
          : int.tryParse('$portValue') ?? 8765;
      if (code.isEmpty || code == _lastDiscoveryCode) return;
      _lastDiscoveryCode = code;
      final existingHost = _hostCtrl.text.trim();
      final configHost = WorkerConnectionConfig.load()?.host.trim() ?? '';
      // Never keep USB-era loopback when discovery reports a LAN peer.
      String host;
      if (existingHost.isNotEmpty &&
          !WorkerConnectionConfig.isLoopbackHost(existingHost)) {
        host = existingHost;
      } else if (configHost.isNotEmpty &&
          !WorkerConnectionConfig.isLoopbackHost(configHost)) {
        host = configHost;
      } else {
        host = WorkerConnectionConfig.normalizeHost(datagram.address.address);
      }
      _hostCtrl.text = host;
      _portCtrl.text = port.toString();
      _codeCtrl.text = code;
      _push(
        'SYSTEM',
        'Discovered Engel PC over WiFi. Auto-pairing.',
        _Palette.green,
      );
      unawaited(_pair());
    } catch (_) {
      // Ignore unrelated LAN broadcasts.
    }
  }

  // Adopt a worker id typed in the UI: persist it and rebuild the client so
  // every later POST identifies as the new worker. Keeps one APK usable for
  // any Engel worker (alpha/beta/gamma/...) without adb provisioning.
  void _adoptWorkerIdFromField() {
    final typed = _workerIdCtrl.text.trim();
    if (typed.isEmpty || typed == _identity.workerId) return;
    if (!WorkerIdentity.idPattern.hasMatch(typed)) {
      _push(
        'SYSTEM',
        'Worker id "$typed" rejected: use lowercase letters, digits and _ '
        '(e.g. android_worker_gamma). Identity unchanged.',
        _Palette.amber,
      );
      _workerIdCtrl.text = _identity.workerId;
      return;
    }
    final name = typed
        .split('_')
        .map((p) => p.isEmpty ? p : '${p[0].toUpperCase()}${p.substring(1)}')
        .join(' ');
    final defaults = WorkerIdentity.defaultsFor(typed);
    setState(() {
      _identity = WorkerIdentity(
        workerId: typed,
        workerName: name,
        phoneModel: _identity.phoneModel,
        agentId: defaults['agent_id']!,
        agentName: defaults['agent_name']!,
        brainId: defaults['brain_id']!,
        brainLabel: defaults['brain_label']!,
        brainLane: defaults['brain_lane']!,
      );
      _currentAgent = defaults['agent_name']!;
      _currentBrain = defaults['brain_label']!;
      _currentTitle = '';
      _discordPipeJob = false;
    });
    _identity.save();
    _client = LanPairingClient(
      workerId: _identity.workerId,
      workerName: _identity.workerName,
      phoneModel: _identity.phoneModel,
    );
    _push(
      'SYSTEM',
      'Worker identity set to ${_identity.workerId} · '
      'Agent: ${_identity.agentName} · Brain: ${_identity.brainLabel}',
      _Palette.green,
    );
  }

  Future<void> _pair() async {
    _adoptWorkerIdFromField();
    final host = WorkerConnectionConfig.normalizeHost(_hostCtrl.text);
    final port = WorkerConnectionConfig.normalizePort(
      int.tryParse(_portCtrl.text.trim()) ??
          WorkerConnectionConfig.canonicalLanPort,
    );
    final code = _codeCtrl.text.trim();
    if (_hostCtrl.text.trim() != host) {
      _hostCtrl.text = host;
    }
    if (_portCtrl.text.trim() != port.toString()) {
      _portCtrl.text = port.toString();
    }
    if (host.isEmpty || code.isEmpty) {
      _push('SYSTEM', 'Need PC host + pairing code.', _Palette.amber);
      return;
    }
    _setConn('PAIRING…', _Palette.amber);
    final res = await _client.testPairing(
      host: host,
      port: port,
      pairingCode: code,
    );
    if (!mounted) return;
    _recordPoll(res.ok);
    if (res.ok) {
      _setConn('PAIRED', _Palette.green);
      _push('PAIRED', res.message, _Palette.green);
      final decoded = res.decodedJson;
      if (decoded != null) {
        final agentName = decoded['agent_name']?.toString().trim() ?? '';
        final brainLabel = decoded['brain_label']?.toString().trim() ?? '';
        if (agentName.isNotEmpty || brainLabel.isNotEmpty) {
          setState(() {
            if (agentName.isNotEmpty) _currentAgent = agentName;
            if (brainLabel.isNotEmpty) _currentBrain = brainLabel;
          });
          _push(
            'AGENT',
            'Bound: ${_currentAgent.isEmpty ? _identity.agentName : _currentAgent} · '
            'Brain: ${_currentBrain.isEmpty ? _identity.brainLabel : _currentBrain}',
            _Palette.cyan,
          );
        }
      }
      WorkerConnectionConfig(
        host: host,
        port: port,
        pairingCode: code,
        autoPair: true,
      ).save();
      _startAutoMode();
    } else {
      _setConn('NOT PAIRED', _Palette.red);
      _push('SYSTEM', 'Pair failed: ${res.message}', _Palette.red);
    }
  }

  Future<void> _testHealth() async {
    final host = WorkerConnectionConfig.normalizeHost(_hostCtrl.text);
    final port = WorkerConnectionConfig.normalizePort(
      int.tryParse(_portCtrl.text.trim()) ??
          WorkerConnectionConfig.canonicalLanPort,
    );
    if (_hostCtrl.text.trim() != host) _hostCtrl.text = host;
    if (_portCtrl.text.trim() != '$port') _portCtrl.text = '$port';
    if (host.isEmpty) {
      _push('SYSTEM', 'PC host required for LAN Pairing.', _Palette.amber);
      return;
    }
    final res = await _client.testHealth(host: host, port: port);
    if (!mounted) return;
    _push('LAN Pairing', res.message, res.ok ? _Palette.green : _Palette.amber);
  }

  void _pauseAutoMode() {
    _autoModeEnabled = false;
    _autoPollTimer?.cancel();
    _autoPollTimer = null;
    _setConn('PAUSED', _Palette.amber);
    _push(
      'Auto Worker',
      'Pause Auto Mode. Check Now remains manual.',
      _Palette.amber,
    );
  }

  void _startAutoMode() {
    _autoModeEnabled = true;
    _autoPollTimer?.cancel();
    _push(
      'Auto Worker',
      'Auto Mode enabled. Polling Meeting Room queue. Wakelock stays active while this app is foreground.',
      _Palette.green,
    );
    unawaited(_pollOnce());
    _autoPollTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      if (_autoModeEnabled) {
        unawaited(_pollOnce());
      }
    });
  }

  void _clearStatus() {
    setState(() {
      _messages.clear();
      // Dedicated Agent+Brain stay assigned; only clear active tasking.
      _currentAgent = _identity.agentName;
      _currentBrain = _identity.brainLabel;
      _currentTitle = '';
      _lastAssignmentId = '';
      _discordPipeJob = false;
    });
  }

  Future<void> _pollOnce() async {
    if (_polling) return;
    final host = WorkerConnectionConfig.normalizeHost(_hostCtrl.text);
    final port = WorkerConnectionConfig.normalizePort(
      int.tryParse(_portCtrl.text.trim()) ??
          WorkerConnectionConfig.canonicalLanPort,
    );
    final code = _codeCtrl.text.trim();
    if (_hostCtrl.text.trim() != host) _hostCtrl.text = host;
    if (_portCtrl.text.trim() != '$port') _portCtrl.text = '$port';
    if (host.isEmpty || code.isEmpty) return;
    _polling = true;
    try {
      final res = await _client.nextAssignment(
        host: host,
        port: port,
        pairingCode: code,
      );
      if (!mounted) return;
      final decoded = res.decodedJson;
      if (!res.ok || decoded == null) {
        _recordPoll(false);
        _setConn('OFFLINE', _Palette.amber);
        return;
      }
      _recordPoll(true);
      _setConn('PAIRED', _Palette.green);

      final status = decoded['status']?.toString();
      if (status == 'no_work') return; // idle; do not spam transcript
      if (status == 'assignment_ready') {
        final assignment = decoded['assignment'];
        if (assignment is Map) {
          final packetId = assignment['packet_id']?.toString() ?? '';
          if (packetId.isNotEmpty && packetId == _lastAssignmentId) return;
          final agentBinding = assignment['agent_binding'];
          final brainBinding = assignment['brain_binding'];
          final origin = assignment['origin'];
          final fromDiscord = origin is Map &&
              origin['source']?.toString() == 'discord_desk';
          String agent = _identity.agentName;
          if (agentBinding is Map &&
              (agentBinding['agent_name']?.toString().trim().isNotEmpty ??
                  false)) {
            agent = agentBinding['agent_name'].toString();
          } else if ((assignment['created_by'] as String?)
                  ?.trim()
                  .isNotEmpty ==
              true) {
            // Prefer dedicated phone agent over generic router label.
            agent = _identity.agentName;
          }
          String brain = _identity.brainLabel;
          if (brainBinding is Map &&
              (brainBinding['brain_label']?.toString().trim().isNotEmpty ??
                  false)) {
            brain = brainBinding['brain_label'].toString();
          }
          final title = (assignment['title'] as String?) ?? 'untitled';
          final instructions = (assignment['instructions'] as String?) ?? '';
          setState(() {
            _currentAgent = agent;
            _currentBrain = brain;
            _currentTitle = title;
            _discordPipeJob = fromDiscord;
            _assignmentsReceived += 1;
          });
          final feedTag = fromDiscord ? 'DISCORD PIPE · $agent' : agent;
          _push(feedTag, '$title\n$instructions', _Palette.green);
          // Return a bounded draft result so the queue advances and Engel can
          // review actual worker output. The result remains untrusted and
          // cannot apply changes, run commands, or write memory.
          unawaited(
            _client
                .returnDraftResult(
                  host: host,
                  port: port,
                  pairingCode: code,
                  assignment: Map<String, Object?>.from(assignment),
                )
                .then((r) {
                  if (r.ok) {
                    // Mark handled only after the receiver accepted the
                    // result; a failed return leaves the packet unclaimed so
                    // the next poll retries instead of dropping it forever.
                    _lastAssignmentId = packetId;
                    if (mounted) {
                      setState(() => _resultsReturned += 1);
                    }
                  } else if (mounted) {
                    _push(
                      'SYSTEM',
                      'Return failed (will retry next poll): ${r.message}',
                      _Palette.amber,
                    );
                  }
                }),
          );
        }
      }
    } finally {
      _polling = false;
    }
  }

  void _setConn(String state, Color color) {
    if (state == 'OFFLINE' || state == 'NOT PAIRED') {
      // Allow the fixed discovery code to trigger auto-pair again once the
      // link drops (receiver restarts reuse the same shared code).
      _lastDiscoveryCode = '';
    }
    setState(() {
      _connState = state;
      _connColor = color;
    });
  }

  void _push(String name, String text, Color color) {
    setState(() {
      _messages.add(
        _Message(name: name, text: text, color: color, time: TimeOfDay.now()),
      );
      if (_messages.length > 200) _messages.removeAt(0);
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_transcriptCtrl.hasClients) {
        _transcriptCtrl.animateTo(
          _transcriptCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  // ─── Avatar-first operator shell ───────────────────────────────────────────
  NewTechTheme get _theme => NewTechTheme.forWorker(_identity.workerId);

  AvatarMood get _avatarMood {
    if (_currentTitle.isNotEmpty) {
      return _discordPipeJob ? AvatarMood.discordPipe : AvatarMood.tasking;
    }
    if (_connState == 'PAIRED') return AvatarMood.ready;
    return AvatarMood.idle;
  }

  void _onAvatarTap() {
    final agent =
        _currentAgent.isNotEmpty ? _currentAgent : _identity.agentName;
    final brain =
        _currentBrain.isNotEmpty ? _currentBrain : _identity.brainLabel;
    final mode = _currentTitle.isNotEmpty
        ? (_discordPipeJob ? 'Discord pipe' : 'Tasking')
        : (_connState == 'PAIRED' ? 'Agent ready' : _connState);
    ScaffoldMessenger.of(context).clearSnackBars();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        backgroundColor: NewTechTheme.surface2,
        content: Text(
          '$mode · $agent · Brain $brain',
          style: const TextStyle(color: NewTechTheme.text, fontSize: 13),
        ),
        duration: const Duration(milliseconds: 1600),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = _theme;
    final hasTask = _currentTitle.isNotEmpty;
    final agent =
        _currentAgent.isNotEmpty ? _currentAgent : _identity.agentName;
    final brain =
        _currentBrain.isNotEmpty ? _currentBrain : _identity.brainLabel;
    final modeLabel = hasTask
        ? (_discordPipeJob ? 'Discord pipe' : 'Tasking')
        : 'Agent ready';
    final modeColor = hasTask ? theme.accent : NewTechTheme.ok;
    final linkPct = (_linkQuality * 100).round();
    final batt = _batteryLevel < 0 ? '--' : '$_batteryLevel%';
    final paired = _connState == 'PAIRED';

    return Scaffold(
      backgroundColor: NewTechTheme.bg,
      resizeToAvoidBottomInset: false,
      body: Stack(
        fit: StackFit.expand,
        children: [
          Positioned.fill(
            child: Image.asset(
              theme.textureAsset,
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => Container(color: NewTechTheme.bg),
            ),
          ),
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  center: const Alignment(0, -0.15),
                  radius: 1.05,
                  colors: [
                    theme.accent.withValues(alpha: 0.10),
                    NewTechTheme.bg.withValues(alpha: 0.72),
                    NewTechTheme.bg.withValues(alpha: 0.96),
                  ],
                ),
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
              child: Column(
                children: [
                  Row(
                    children: [
                      QuietLabel('Engel · ${theme.label}'),
                      const Spacer(),
                      Text(
                        _identity.phoneModel,
                        style: const TextStyle(
                          color: NewTechTheme.muted,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        WorkerAvatarStage(
                          theme: theme,
                          mood: _avatarMood,
                          breath: _pulse,
                          onTap: _onAvatarTap,
                          faceLight: _faceLight,
                          size: MediaQuery.sizeOf(context).shortestSide * 0.58,
                        ),
                        const SizedBox(height: 14),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 5,
                          ),
                          decoration: BoxDecoration(
                            color: modeColor.withValues(alpha: 0.14),
                            borderRadius: BorderRadius.circular(999),
                            border: Border.all(
                              color: modeColor.withValues(alpha: 0.45),
                            ),
                          ),
                          child: Text(
                            modeLabel.toUpperCase(),
                            style: TextStyle(
                              color: modeColor,
                              fontSize: 11,
                              letterSpacing: 1.3,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          agent,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: NewTechTheme.text,
                            fontSize: 20,
                            fontWeight: FontWeight.w700,
                            height: 1.15,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Brain · $brain',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            color: theme.accent,
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        if (hasTask) ...[
                          const SizedBox(height: 8),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            child: Text(
                              _currentTitle,
                              textAlign: TextAlign.center,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: NewTechTheme.muted,
                                fontSize: 13,
                                height: 1.3,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  Wrap(
                    alignment: WrapAlignment.center,
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      HudChromeChip(
                        label: 'Link',
                        value: paired ? '$linkPct%' : _connState,
                        accent: paired ? NewTechTheme.ok : NewTechTheme.warn,
                      ),
                      HudChromeChip(
                        label: 'Power',
                        value: batt,
                        accent: theme.accent,
                      ),
                      HudChromeChip(
                        label: 'Tasks',
                        value: '$_assignmentsReceived',
                      ),
                      HudChromeChip(
                        label: 'Drafts',
                        value: '$_resultsReturned',
                        accent: theme.accent,
                      ),
                      HudChromeChip(
                        label: 'Pair',
                        value: paired ? 'ON' : 'OFF',
                        accent: paired ? NewTechTheme.ok : NewTechTheme.warn,
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  _ntControlsCollapsed(theme),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _ntControlsCollapsed(NewTechTheme theme) {
    InputDecoration deco(String hint) => InputDecoration(
          hintText: hint,
          hintStyle: const TextStyle(color: NewTechTheme.muted, fontSize: 13),
          filled: true,
          fillColor: NewTechTheme.surface2,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: NewTechTheme.border),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: NewTechTheme.border),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: BorderSide(color: theme.accent),
          ),
        );

    Widget ghost(String label, VoidCallback onTap) {
      return Expanded(
        child: OutlinedButton(
          onPressed: onTap,
          style: OutlinedButton.styleFrom(
            foregroundColor: NewTechTheme.text,
            side: const BorderSide(color: NewTechTheme.border),
            padding: const EdgeInsets.symmetric(vertical: 10),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
          ),
          child: Text(label, style: const TextStyle(fontSize: 12)),
        ),
      );
    }

    return Theme(
      data: ThemeData(
        dividerColor: Colors.transparent,
        splashColor: theme.accentSoft,
      ),
      child: SoftPanel(
        padding: EdgeInsets.zero,
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 14),
          childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          iconColor: NewTechTheme.muted,
          collapsedIconColor: NewTechTheme.muted,
          title: QuietLabel('Controls · ${_identity.workerId}'),
          subtitle: const Text(
            'Pairing status-only · review drafts · no Discord on phone',
            style: TextStyle(color: NewTechTheme.muted, fontSize: 11),
          ),
          children: [
            Row(
              children: [
                const QuietLabel('Face light'),
                const Spacer(),
                Text(
                  '${(_faceLight * 100).round()}%',
                  style: TextStyle(
                    color: theme.accent,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            SliderTheme(
              data: SliderTheme.of(context).copyWith(
                activeTrackColor: theme.accent,
                inactiveTrackColor: NewTechTheme.border,
                thumbColor: theme.accent,
                overlayColor: theme.accentSoft,
              ),
              child: Slider(
                value: _faceLight,
                min: 0,
                max: 1,
                divisions: 20,
                label: 'Face light ${(_faceLight * 100).round()}%',
                onChanged: (value) {
                  setState(() => _faceLight = value);
                },
                onChangeEnd: (value) {
                  unawaited(_persistFaceLight(value));
                },
              ),
            ),
            Text(
              'Low = eyes only in the dark · High = full sleek portrait',
              style: TextStyle(
                color: NewTechTheme.muted.withValues(alpha: 0.9),
                fontSize: 11,
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _workerIdCtrl,
              style: const TextStyle(color: NewTechTheme.text, fontSize: 14),
              decoration: deco('worker id'),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  flex: 3,
                  child: TextField(
                    controller: _hostCtrl,
                    style:
                        const TextStyle(color: NewTechTheme.text, fontSize: 14),
                    decoration: deco('PC host'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  flex: 2,
                  child: TextField(
                    controller: _portCtrl,
                    style:
                        const TextStyle(color: NewTechTheme.text, fontSize: 14),
                    decoration: deco('port'),
                    keyboardType: TextInputType.number,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  flex: 2,
                  child: TextField(
                    controller: _codeCtrl,
                    style:
                        const TextStyle(color: NewTechTheme.text, fontSize: 14),
                    decoration: deco('pair code'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: () => unawaited(_pair()),
                style: FilledButton.styleFrom(
                  backgroundColor: theme.accent,
                  foregroundColor: NewTechTheme.bg,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
                child: const Text(
                  'Test Pairing',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                ghost('Health', () => unawaited(_testHealth())),
                const SizedBox(width: 8),
                ghost('Check', () => unawaited(_pollOnce())),
                const SizedBox(width: 8),
                ghost(
                  _autoModeEnabled ? 'Pause' : 'Auto',
                  () {
                    if (_autoModeEnabled) {
                      _pauseAutoMode();
                    } else {
                      _startAutoMode();
                    }
                  },
                ),
                const SizedBox(width: 8),
                ghost('Clear', _clearStatus),
              ],
            ),
            const SizedBox(height: 8),
            const Text(
              'Pairing is status-only. Approved packets only. '
              'Untrusted draft return. Phone does not control Engel.',
              style: TextStyle(
                color: NewTechTheme.muted,
                fontSize: 11,
                height: 1.35,
              ),
            ),
            if (_messages.isNotEmpty) ...[
              const SizedBox(height: 10),
              const QuietLabel('Recent'),
              const SizedBox(height: 6),
              SizedBox(
                height: 88,
                child: ListView.builder(
                  controller: _transcriptCtrl,
                  itemCount: _messages.length,
                  itemBuilder: (context, index) {
                    final m = _messages[index];
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Text(
                        '${m.name}: ${m.text}',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: NewTechTheme.muted,
                          fontSize: 12,
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

}

class _Message {
  const _Message({
    required this.name,
    required this.text,
    required this.color,
    required this.time,
  });
  final String name;
  final String text;
  final Color color;
  final TimeOfDay time;
}

// ─── HUD building blocks ─────────────────────────────────────────────────────

class _ModeChip extends StatelessWidget {
  const _ModeChip(this.label);
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
      decoration: BoxDecoration(
        color: _Palette.card2,
        border: Border.all(color: _Palette.border),
        borderRadius: BorderRadius.circular(2),
      ),
      child: Text(
        label,
        style: _mono.copyWith(color: _Palette.dim, fontSize: 8),
      ),
    );
  }
}

class _BlinkDot extends StatelessWidget {
  const _BlinkDot({
    required this.pulse,
    required this.color,
    required this.active,
  });
  final Animation<double> pulse;
  final Color color;
  final bool active;

  @override
  Widget build(BuildContext context) {
    // RepaintBoundary keeps the per-frame pulse repaint inside this 8px dot
    // instead of bubbling to the root and repainting the whole foreground.
    return RepaintBoundary(
      child: AnimatedBuilder(
      animation: pulse,
      builder: (context, _) {
        final glow = active ? 0.35 + pulse.value * 0.65 : 0.5;
        return Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: color.withValues(alpha: glow),
            boxShadow: active
                ? [
                    BoxShadow(
                      color: color.withValues(alpha: glow * 0.8),
                      blurRadius: 8,
                      spreadRadius: 1,
                    ),
                  ]
                : const [],
          ),
        );
      },
      ),
    );
  }
}

/// Cut-corner HUD panel with corner brackets and an accent edge.
class _TechFrame extends StatelessWidget {
  const _TechFrame({
    required this.child,
    required this.borderColor,
    required this.accent,
    this.padding = const EdgeInsets.all(10),
  });
  final Widget child;
  final Color borderColor;
  final Color accent;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _TechFramePainter(borderColor: borderColor, accent: accent),
      child: Padding(padding: padding, child: child),
    );
  }
}

class _TechFramePainter extends CustomPainter {
  _TechFramePainter({required this.borderColor, required this.accent});
  final Color borderColor;
  final Color accent;

  @override
  void paint(Canvas canvas, Size size) {
    const cut = 10.0;
    final w = size.width;
    final h = size.height;
    final path = Path()
      ..moveTo(cut, 0)
      ..lineTo(w, 0)
      ..lineTo(w, h - cut)
      ..lineTo(w - cut, h)
      ..lineTo(0, h)
      ..lineTo(0, cut)
      ..close();

    canvas.drawPath(
      path,
      Paint()..color = _Palette.card.withValues(alpha: 0.88),
    );
    canvas.drawPath(
      path,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = borderColor,
    );

    // Accent edge along the top-left cut + corner brackets.
    final accentPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6
      ..color = accent.withValues(alpha: 0.9);
    canvas.drawLine(Offset(0, cut), Offset(cut, 0), accentPaint);
    const b = 7.0;
    canvas.drawPath(
      Path()
        ..moveTo(w - b, 0)
        ..lineTo(w, 0)
        ..lineTo(w, b),
      accentPaint,
    );
    canvas.drawPath(
      Path()
        ..moveTo(0, h - b)
        ..lineTo(0, h)
        ..lineTo(b, h),
      accentPaint,
    );
  }

  @override
  bool shouldRepaint(_TechFramePainter old) =>
      old.borderColor != borderColor || old.accent != accent;
}

/// Static backdrop grid: painted ONCE (no repaint listenable) so the ~40 grid
/// lines never re-raster every frame. Only _ScanlinePainter animates.
class _GridPainter extends CustomPainter {
  const _GridPainter();

  static final Paint _grid = Paint()
    ..strokeWidth = 0.5
    ..color = _Palette.green.withValues(alpha: 0.045);

  @override
  void paint(Canvas canvas, Size size) {
    const step = 30.0;
    for (double x = 0; x < size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), _grid);
    }
    for (double y = 0; y < size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), _grid);
    }
  }

  @override
  bool shouldRepaint(_GridPainter old) => false;
}

/// The moving scanline band only — a single thin gradient rect per frame,
/// far cheaper than redrawing the whole grid every tick.
class _ScanlinePainter extends CustomPainter {
  _ScanlinePainter({required this.animation}) : super(repaint: animation);
  final Animation<double> animation;

  static const _colors = [
    Color(0x0000E87A),
    Color(0x1400E87A),
    Color(0x0000E87A),
  ];

  @override
  void paint(Canvas canvas, Size size) {
    final y = size.height * animation.value;
    final rect = Rect.fromLTWH(0, y - 40, size.width, 80);
    canvas.drawRect(
      rect,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: _colors,
        ).createShader(rect),
    );
  }

  @override
  bool shouldRepaint(_ScanlinePainter old) => false;
}

/// Rotating radar sweep — spins while paired, static when idle.
class _RadarPainter extends CustomPainter {
  _RadarPainter({
    required this.animation,
    required this.color,
    required this.active,
  }) : super(repaint: animation);
  final Animation<double> animation;
  final Color color;
  final bool active;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 2;
    final ring = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = color.withValues(alpha: 0.35);
    canvas.drawCircle(center, radius, ring);
    canvas.drawCircle(center, radius * 0.62, ring);
    canvas.drawCircle(center, radius * 0.28, ring);
    final cross = Paint()
      ..strokeWidth = 0.6
      ..color = color.withValues(alpha: 0.2);
    canvas.drawLine(
      Offset(center.dx - radius, center.dy),
      Offset(center.dx + radius, center.dy),
      cross,
    );
    canvas.drawLine(
      Offset(center.dx, center.dy - radius),
      Offset(center.dx, center.dy + radius),
      cross,
    );

    if (active) {
      final angle = animation.value * 2 * math.pi;
      canvas.save();
      canvas.translate(center.dx, center.dy);
      canvas.rotate(angle);
      final sweep = Paint()
        ..shader = SweepGradient(
          startAngle: 0,
          endAngle: math.pi / 2,
          colors: [
            color.withValues(alpha: 0),
            color.withValues(alpha: 0.5),
          ],
        ).createShader(
          Rect.fromCircle(center: Offset.zero, radius: radius),
        );
      canvas.drawPath(
        Path()
          ..moveTo(0, 0)
          ..arcTo(
            Rect.fromCircle(center: Offset.zero, radius: radius),
            0,
            math.pi / 2,
            false,
          )
          ..close(),
        sweep,
      );
      canvas.restore();
    }
    canvas.drawCircle(
      center,
      2.5,
      Paint()..color = color.withValues(alpha: 0.9),
    );
  }

  @override
  bool shouldRepaint(_RadarPainter old) =>
      old.color != color || old.active != active;
}

/// 270° arc gauge with glow; value and caption drawn in the center.
class _ArcGauge extends StatelessWidget {
  const _ArcGauge({
    required this.value,
    required this.color,
    required this.pulse,
    required this.label,
    required this.caption,
  });
  final double value;
  final Color color;
  final Animation<double> pulse;
  final String label;
  final String caption;

  @override
  Widget build(BuildContext context) {
    // RepaintBoundary confines the per-frame gauge-glow repaint to this cell
    // instead of forcing the whole foreground (panels, text, feed) to repaint.
    return RepaintBoundary(
      child: AnimatedBuilder(
      animation: pulse,
      builder: (context, _) {
        return CustomPaint(
          painter: _ArcGaugePainter(
            value: value.clamp(0.0, 1.0),
            color: color,
            glow: 0.25 + pulse.value * 0.35,
          ),
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  label,
                  style: _mono.copyWith(
                    color: color,
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  caption,
                  style: _mono.copyWith(
                    color: _Palette.dim,
                    fontSize: 8,
                    letterSpacing: 2,
                  ),
                ),
              ],
            ),
          ),
        );
      },
      ),
    );
  }
}

class _ArcGaugePainter extends CustomPainter {
  _ArcGaugePainter({
    required this.value,
    required this.color,
    required this.glow,
  });
  final double value;
  final Color color;
  final double glow;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 6;
    final rect = Rect.fromCircle(center: center, radius: radius);
    const start = 3 * math.pi / 4;
    const total = 3 * math.pi / 2;
    canvas.drawArc(
      rect,
      start,
      total,
      false,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 4
        ..strokeCap = StrokeCap.round
        ..color = _Palette.border2,
    );
    if (value > 0) {
      // Glow pass then solid pass.
      canvas.drawArc(
        rect,
        start,
        total * value,
        false,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 7
          ..strokeCap = StrokeCap.round
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5)
          ..color = color.withValues(alpha: glow),
      );
      canvas.drawArc(
        rect,
        start,
        total * value,
        false,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 4
          ..strokeCap = StrokeCap.round
          ..color = color,
      );
    }
  }

  @override
  bool shouldRepaint(_ArcGaugePainter old) =>
      old.value != value || old.color != color || old.glow != glow;
}

/// Neon sparkline of recent poll results; failures render as red baseline dots.
class _SparklinePainter extends CustomPainter {
  _SparklinePainter({
    required this.history,
    required this.color,
    required this.failColor,
  });
  final List<double> history;
  final Color color;
  final Color failColor;

  @override
  void paint(Canvas canvas, Size size) {
    if (history.isEmpty) {
      final base = Paint()
        ..strokeWidth = 0.8
        ..color = _Palette.border2;
      canvas.drawLine(
        Offset(0, size.height - 2),
        Offset(size.width, size.height - 2),
        base,
      );
      return;
    }
    final n = history.length;
    final dx = n > 1 ? size.width / (n - 1) : size.width;
    final path = Path();
    for (var i = 0; i < n; i++) {
      final x = n > 1 ? i * dx : size.width / 2;
      final y = 2 + (1 - history[i]) * (size.height - 4);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
      if (history[i] == 0.0) {
        canvas.drawCircle(
          Offset(x, size.height - 2),
          1.6,
          Paint()..color = failColor,
        );
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3)
        ..color = color.withValues(alpha: 0.35),
    );
    canvas.drawPath(
      path,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2
        ..color = color,
    );
  }

  @override
  bool shouldRepaint(_SparklinePainter old) {
    // Once _pollHistory saturates at its 48 cap the length stops changing and
    // the window scrolls in place, so a length/last-value check would freeze
    // the sparkline. This painter is only rebuilt on poll events (~5s apart),
    // never per frame, so an element-wise compare is cheap and correct.
    if (old.history.length != history.length) return true;
    for (var i = 0; i < history.length; i++) {
      if (old.history[i] != history[i]) return true;
    }
    return false;
  }
}

/// Self-ticking session uptime readout (isolated so the page doesn't rebuild).
class _UptimeText extends StatefulWidget {
  const _UptimeText({required this.start});
  final DateTime start;

  @override
  State<_UptimeText> createState() => _UptimeTextState();
}

class _UptimeTextState extends State<_UptimeText> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final d = DateTime.now().difference(widget.start);
    String two(int v) => v.toString().padLeft(2, '0');
    final text =
        '${two(d.inHours)}:${two(d.inMinutes % 60)}:${two(d.inSeconds % 60)}';
    return Text(
      text,
      style: _mono.copyWith(
        color: _Palette.text,
        fontSize: 14,
        fontWeight: FontWeight.w800,
        letterSpacing: 1,
      ),
    );
  }
}
