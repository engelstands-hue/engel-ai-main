import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:archive/archive.dart';
import 'package:battery_plus/battery_plus.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:crypto/crypto.dart';
import 'package:csv/csv.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:graphs/graphs.dart';
import 'package:html_unescape/html_unescape.dart';
import 'package:image/image.dart' as img;
import 'package:multicast_dns/multicast_dns.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:sensors_plus/sensors_plus.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import 'package:yaml/yaml.dart';

class WorkerCapabilityProbe {
  const WorkerCapabilityProbe();

  Future<Map<String, Object?>> collect({
    required String workerId,
    required String workerName,
    required String phoneModel,
  }) async {
    final packageInfo = await _packageInfo();
    final battery = await _batteryInfo();
    final connectivity = await _connectivityInfo();
    final android = await _androidInfo();
    final storage = await _storageInfo();
    final sensors = await _sensorInfo();
    final wakelock = await _wakelockInfo();
    final creation = await _creationInfo(workerId);
    final pluginUpgrades = await _pluginUpgradeInfo(workerId);
    final processors = Platform.numberOfProcessors;

    final snapshot = <String, Object?>{
      'schema_version': '1',
      'worker_id': workerId,
      'worker_name': workerName,
      'configured_phone_model': phoneModel,
      'platform': Platform.operatingSystem,
      'platform_version': Platform.operatingSystemVersion,
      'cpu_cores': processors,
      'app': packageInfo,
      'android': android,
      'battery': battery,
      'connectivity': connectivity,
      'storage': storage,
      'sensors': sensors,
      'wakelock': wakelock,
      'creation': creation,
      'plugin_upgrades': pluginUpgrades,
      'code_and_search': <String, Object?>{
        'candidate_code_drafting': true,
        'python_candidate_drafting': true,
        'dart_candidate_drafting': true,
        'dart_formatting': true,
        'reviewable_diffs': true,
        'bounded_https_search': true,
        'html_result_parsing': true,
        'markdown_rendering': true,
        'sha256_integrity_hashing': true,
        'zip_artifact_bundling': true,
        'csv_table_drafting': true,
        'yaml_config_parsing': true,
        'graph_ordering_algorithms': true,
        'html_entity_cleanup': true,
        'mdns_client_available': true,
        'executes_code': false,
        'writes_source': false,
      },
      'safe_worker_contract': <String, Object?>{
        'candidate_outputs_only': true,
        'trusted_memory_write': false,
        'source_mutation': false,
        'route_mutation': false,
        'provider_runtime': false,
        'raw_shell_execution': false,
        'wifi_adb': false,
      },
      'allowed_task_types': <String>[
        'summarize_text',
        'draft_research_note',
        'draft_candidate_json',
        'format_report_draft',
        'classify_file',
        'compute_small_local_task',
        'conical_requirements_analysis',
        'conical_verification_plan',
        'conical_dependency_risk_check',
        'return_status',
        'return_logs',
        'return_receipt',
        'draft_code_artifact',
        'web_research_brief',
      ],
      'best_for': _bestFor(
        processors,
        android,
        sensors,
        storage,
        creation,
        pluginUpgrades,
      ),
    };
    snapshot['local_snapshot'] = await _writeLocalSnapshot(workerId, snapshot);
    return snapshot;
  }

  Future<Map<String, Object?>> _packageInfo() async {
    try {
      final info = await PackageInfo.fromPlatform();
      return <String, Object?>{
        'app_name': info.appName,
        'package_name': info.packageName,
        'version': info.version,
        'build_number': info.buildNumber,
      };
    } catch (error) {
      return <String, Object?>{'error': '$error'};
    }
  }

  Future<Map<String, Object?>> _batteryInfo() async {
    try {
      final battery = Battery();
      final level = await battery.batteryLevel;
      final state = await battery.batteryState;
      final saver = await battery.isInBatterySaveMode;
      return <String, Object?>{
        'level_percent': level,
        'state': state.name,
        'battery_save_mode': saver,
      };
    } catch (error) {
      return <String, Object?>{'error': '$error'};
    }
  }

  Future<Map<String, Object?>> _connectivityInfo() async {
    try {
      final results = await Connectivity().checkConnectivity();
      return <String, Object?>{
        'transports': results.map((item) => item.name).toList(growable: false),
        'wifi_or_lan_ready':
            results.contains(ConnectivityResult.wifi) ||
            results.contains(ConnectivityResult.ethernet),
      };
    } catch (error) {
      return <String, Object?>{'error': '$error'};
    }
  }

  Future<Map<String, Object?>> _storageInfo() async {
    final out = <String, Object?>{};
    try {
      final support = await getApplicationSupportDirectory();
      await support.create(recursive: true);
      out['app_support_available'] = true;
      out['app_support_path'] = support.path;
    } catch (error) {
      out['app_support_available'] = false;
      out['app_support_error'] = '$error';
    }
    try {
      final temp = await getTemporaryDirectory();
      out['temp_available'] = true;
      out['temp_path'] = temp.path;
    } catch (error) {
      out['temp_available'] = false;
      out['temp_error'] = '$error';
    }
    return out;
  }

  Future<Map<String, Object?>> _sensorInfo() async {
    return <String, Object?>{
      'accelerometer': await _probeSensor(
        accelerometerEventStream(samplingPeriod: SensorInterval.uiInterval),
      ),
      'gyroscope': await _probeSensor(
        gyroscopeEventStream(samplingPeriod: SensorInterval.uiInterval),
      ),
      'magnetometer': await _probeSensor(
        magnetometerEventStream(samplingPeriod: SensorInterval.uiInterval),
      ),
      'barometer': await _probeSensor(
        barometerEventStream(samplingPeriod: SensorInterval.normalInterval),
      ),
    };
  }

  Future<Map<String, Object?>> _probeSensor(Stream<Object> stream) async {
    try {
      final event = await stream.first.timeout(
        const Duration(milliseconds: 650),
      );
      return <String, Object?>{'available': true, 'sample': '$event'};
    } on TimeoutException {
      return <String, Object?>{
        'available': false,
        'reason': 'timeout_no_sample',
      };
    } catch (error) {
      return <String, Object?>{'available': false, 'reason': '$error'};
    }
  }

  Future<Map<String, Object?>> _wakelockInfo() async {
    try {
      await WakelockPlus.enable();
      return <String, Object?>{
        'screen_wakelock_enabled': await WakelockPlus.enabled,
      };
    } catch (error) {
      return <String, Object?>{
        'screen_wakelock_enabled': false,
        'error': '$error',
      };
    }
  }

  Future<Map<String, Object?>> _creationInfo(String workerId) async {
    final out = <String, Object?>{
      'pdf_generation': false,
      'png_generation': false,
      'artifact_storage': 'app_private_only',
    };
    try {
      final support = await getApplicationSupportDirectory();
      final dir = Directory('${support.path}/engel_creation_artifacts');
      await dir.create(recursive: true);
      final stamp = DateTime.now()
          .toUtc()
          .toIso8601String()
          .replaceAll(':', '')
          .replaceAll('.', '_');

      final document = pw.Document();
      document.addPage(
        pw.Page(
          pageFormat: PdfPageFormat.a5,
          build: (context) => pw.Column(
            crossAxisAlignment: pw.CrossAxisAlignment.start,
            children: [
              pw.Text('Engel Worker Capability Artifact'),
              pw.SizedBox(height: 12),
              pw.Text('worker_id: $workerId'),
              pw.Text('created_at_utc: $stamp'),
              pw.Text('status: candidate-only local PDF generation works'),
            ],
          ),
        ),
      );
      final pdfFile = File('${dir.path}/${stamp}_${workerId}_sample.pdf');
      await pdfFile.writeAsBytes(await document.save());
      out['pdf_generation'] = true;
      out['pdf_path'] = pdfFile.path;
      out['pdf_bytes'] = await pdfFile.length();

      final image = img.Image(width: 96, height: 96);
      for (final pixel in image) {
        pixel
          ..r = pixel.x * 2
          ..g = pixel.y * 2
          ..b = 120;
      }
      final pngFile = File('${dir.path}/${stamp}_${workerId}_sample.png');
      await pngFile.writeAsBytes(img.encodePng(image));
      out['png_generation'] = true;
      out['png_path'] = pngFile.path;
      out['png_bytes'] = await pngFile.length();
    } catch (error) {
      out['error'] = '$error';
    }
    return out;
  }

  Future<Map<String, Object?>> _pluginUpgradeInfo(String workerId) async {
    final out = <String, Object?>{
      'source': 'pub.dev_reviewed_safe_pure_dart_set',
      'artifact_storage': 'app_private_or_memory_only',
      'background_runtime_enabled': false,
      'raw_execution_enabled': false,
    };
    try {
      final manifest = [
        'worker_id: $workerId',
        'mode: candidate_only',
        'trust: untrusted_until_engel_review',
      ].join('\n');
      final parsedYaml = loadYaml(manifest);
      out['yaml_parse'] =
          parsedYaml is YamlMap && parsedYaml['worker_id'] == workerId;

      final csvText = csv.encode(<List<Object?>>[
        <Object?>['worker_id', 'capability'],
        <Object?>[workerId, 'plugin_upgrade_probe'],
      ]);
      final csvRows = csv.decode(csvText);
      out['csv_roundtrip'] = csvRows.length == 2 && csvRows[1][0] == workerId;
      out['csv_bytes'] = utf8.encode(csvText).length;

      final digest = sha256.convert(utf8.encode('$manifest\n$csvText'));
      out['sha256'] = digest.toString();

      final bundle = Archive()
        ..addFile(ArchiveFile.string('manifest.yml', manifest))
        ..addFile(ArchiveFile.string('capabilities.csv', csvText));
      final zipBytes = ZipEncoder().encodeBytes(bundle);
      out['zip_bundle'] = zipBytes.isNotEmpty;
      out['zip_bundle_bytes'] = zipBytes.length;

      final order = topologicalSort<String>(
        <String>['engel', 'meeting_room', 'phone_worker', 'candidate_result'],
        (node) => switch (node) {
          'candidate_result' => <String>['phone_worker'],
          'phone_worker' => <String>['meeting_room'],
          'meeting_room' => <String>['engel'],
          _ => <String>[],
        },
      );
      out['graph_ordering'] = order;

      out['html_unescape'] =
          HtmlUnescape().convert('Engel &amp; agents') == 'Engel & agents';

      MDnsClient();
      out['mdns_client_constructed'] = true;
      out['mdns_client_started'] = false;
    } catch (error) {
      out['error'] = '$error';
    }
    return out;
  }

  Future<Map<String, Object?>> _androidInfo() async {
    if (!Platform.isAndroid) return <String, Object?>{};
    try {
      final info = await DeviceInfoPlugin().androidInfo;
      return <String, Object?>{
        'brand': info.brand,
        'manufacturer': info.manufacturer,
        'model': info.model,
        'device': info.device,
        'product': info.product,
        'hardware': info.hardware,
        'sdk_int': info.version.sdkInt,
        'release': info.version.release,
        'supported_abis': info.supportedAbis,
        'is_physical_device': info.isPhysicalDevice,
      };
    } catch (error) {
      return <String, Object?>{'error': '$error'};
    }
  }

  Future<Map<String, Object?>> _writeLocalSnapshot(
    String workerId,
    Map<String, Object?> snapshot,
  ) async {
    try {
      final support = await getApplicationSupportDirectory();
      final dir = Directory('${support.path}/engel_capability_snapshots');
      await dir.create(recursive: true);
      final file = File(
        '${dir.path}/${DateTime.now().toUtc().toIso8601String().replaceAll(':', '').replaceAll('.', '_')}_$workerId.json',
      );
      await file.writeAsString(
        const JsonEncoder.withIndent('  ').convert(snapshot),
      );
      return <String, Object?>{'written': true, 'path': file.path};
    } catch (error) {
      return <String, Object?>{'written': false, 'error': '$error'};
    }
  }

  List<String> _bestFor(
    int processors,
    Map<String, Object?> android,
    Map<String, Object?> sensors,
    Map<String, Object?> storage,
    Map<String, Object?> creation,
    Map<String, Object?> pluginUpgrades,
  ) {
    final sdk = android['sdk_int'];
    final sdkInt = sdk is int ? sdk : 0;
    final labels = <String>{
      'bounded LAN communication',
      'candidate draft returns',
      'classification and labels',
    };
    if (processors >= 6) {
      labels.add('small local compute');
      labels.add('summaries and report drafts');
    }
    if (sdkInt >= 31) {
      labels.add('newer Android API compatibility testing');
    }
    if (storage['app_support_available'] == true) {
      labels.add('app-private audit snapshots');
    }
    if (_sensorAvailable(sensors, 'accelerometer') ||
        _sensorAvailable(sensors, 'gyroscope') ||
        _sensorAvailable(sensors, 'magnetometer')) {
      labels.add('physical-device sensor checks');
    }
    labels.add('candidate Python/code drafting');
    labels.add('bounded web research briefs');
    if (creation['pdf_generation'] == true) {
      labels.add('candidate PDF artifact creation');
    }
    if (creation['png_generation'] == true) {
      labels.add('candidate PNG/image artifact creation');
    }
    if (pluginUpgrades['zip_bundle'] == true) {
      labels.add('candidate ZIP artifact bundles');
    }
    if (pluginUpgrades['csv_roundtrip'] == true) {
      labels.add('candidate CSV data tables');
    }
    if (pluginUpgrades['yaml_parse'] == true) {
      labels.add('YAML/config parsing');
    }
    if (pluginUpgrades['sha256'] is String) {
      labels.add('SHA-256 integrity hashing');
    }
    if (pluginUpgrades['graph_ordering'] is List) {
      labels.add('graph dependency ordering');
    }
    if (pluginUpgrades['mdns_client_constructed'] == true) {
      labels.add('LAN discovery client readiness');
    }
    return labels.toList(growable: false)..sort();
  }

  bool _sensorAvailable(Map<String, Object?> sensors, String key) {
    final value = sensors[key];
    return value is Map && value['available'] == true;
  }
}
