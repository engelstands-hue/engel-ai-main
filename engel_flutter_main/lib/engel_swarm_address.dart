class EngelReachAction {
  const EngelReachAction(this.id, this.label);

  final String id;
  final String label;
}

class EngelDeviceReach {
  const EngelDeviceReach({
    required this.what,
    required this.where,
    required this.actions,
  });

  final String what;
  final String where;
  final List<EngelReachAction> actions;
}

String engelSwarmShortName({
  required String id,
  required String name,
  required String kindLabel,
}) {
  return switch (id) {
    'engel-spine-01' => 'PowerEdge',
    'local-llm-runtime' => 'CT246',
    'meeting-room-server' => 'Meeting',
    'engel-main-pc' => 'This PC',
    'sub-engel-node' => 'Sub-Engel',
    'lan-gateway' || 'wifi-main' => 'Gateway',
    'android_worker_alpha' => 'Alpha',
    'android_worker_beta' => 'Beta',
    'android_worker_gamma' => 'Gamma',
    _ => name.toLowerCase().contains('roku')
        ? 'Roku TV'
        : name.toLowerCase().contains('vizio')
        ? 'Vizio TV'
        : name.startsWith('Unassigned')
        ? kindLabel
        : name,
  };
}

String engelDeviceWhere(String physicalLocation, String placeOverride) {
  final chosen = placeOverride.trim();
  if (chosen.isNotEmpty) return chosen;
  final text = physicalLocation.trim();
  if (text.isEmpty || text.toLowerCase() == 'unknown') return 'Place not set';
  final head = text.split(';').first.trim();
  final lower = text.toLowerCase();
  if (lower.contains('not assigned') || lower.contains('room not')) {
    return '$head. Room not set.';
  }
  return text;
}

EngelDeviceReach engelDeviceReach({
  required String id,
  required String name,
  required String hardware,
  required String physicalLocation,
  required String kindLabel,
  required String kindDetail,
  String placeOverride = '',
}) {
  final machine = hardware.trim().isNotEmpty ? hardware.trim() : name.trim();
  final what = machine.isEmpty ? '$kindLabel. $kindDetail' : '$kindLabel. $machine';
  final actions = <EngelReachAction>[
    if (id.startsWith('android_worker'))
      const EngelReachAction('view-phone', 'View phone'),
    if (id == 'engel-spine-01' || id == 'local-llm-runtime')
      const EngelReachAction('open-chat', 'Open server chat'),
    if (id == 'engel-spine-01' ||
        id == 'local-llm-runtime' ||
        id == 'meeting-room-server')
      const EngelReachAction('open-meeting', 'Open meeting room'),
    if (id == 'sub-engel-node')
      const EngelReachAction('open-sub-engel', 'Open Sub-Engel'),
    if (kindLabel == 'Not identified' || kindLabel == 'Windows computer')
      const EngelReachAction('read-name', 'Read name'),
    const EngelReachAction('set-place', 'Set place'),
  ];
  return EngelDeviceReach(
    what: what,
    where: engelDeviceWhere(physicalLocation, placeOverride),
    actions: actions,
  );
}

String engelNetbiosName(String evidence) {
  final match = RegExp(
    r'^([A-Za-z0-9_-]{1,15})\s+<00>',
    multiLine: true,
  ).firstMatch(evidence);
  return match?.group(1) ?? '';
}

class EngelAddressKind {
  const EngelAddressKind({
    required this.label,
    required this.detail,
    required this.server,
  });

  final String label;
  final String detail;
  final bool server;
}

EngelAddressKind engelAddressKind({
  required String id,
  required String name,
  required String type,
  required String role,
  required String classification,
  required String hardware,
  String evidence = '',
  int sameAdapter = 1,
}) {
  final text = '$name $hardware $evidence'.toLowerCase();
  final EngelAddressKind kind;
  if (id == 'engel-spine-01' ||
      text.contains('poweredge') ||
      text.contains('proxmox')) {
    kind = const EngelAddressKind(
      label: 'Server',
      detail: 'Dell PowerEdge host.',
      server: true,
    );
  } else if (id == 'meeting-room-server' || text.contains('meeting room')) {
    kind = const EngelAddressKind(
      label: 'Server',
      detail: 'Meeting Room service on the Engel server.',
      server: true,
    );
  } else if (id == 'local-llm-runtime' || role == 'model-runtime') {
    kind = const EngelAddressKind(
      label: 'Server',
      detail: 'Model runtime on the Engel server.',
      server: true,
    );
  } else if (type == 'server' ||
      classification == 'logical_runtime' ||
      role.contains('server')) {
    kind = const EngelAddressKind(
      label: 'Server',
      detail: 'Engel server service.',
      server: true,
    );
  } else if (id.startsWith('android_worker') || type == 'android') {
    kind = const EngelAddressKind(
      label: 'Phone',
      detail: 'Engel phone worker.',
      server: false,
    );
  } else if (id == 'lan-gateway' ||
      id == 'wifi-main' ||
      role.contains('gateway')) {
    kind = const EngelAddressKind(
      label: 'Gateway',
      detail: 'LAN gateway.',
      server: false,
    );
  } else if (text.contains('roku') ||
      text.contains('vizio') ||
      text.contains('television') ||
      text.contains('smartcast')) {
    kind = const EngelAddressKind(
      label: 'Television',
      detail: 'Television on the LAN.',
      server: false,
    );
  } else if (text.contains('windows')) {
    kind = const EngelAddressKind(
      label: 'Windows computer',
      detail: 'Windows computer.',
      server: false,
    );
  } else if (type == 'windows' || id == 'engel-main-pc' || type == 'sub_engel') {
    kind = const EngelAddressKind(
      label: 'Computer',
      detail: 'Computer on this network.',
      server: false,
    );
  } else {
    kind = const EngelAddressKind(
      label: 'Not identified',
      detail: 'Seen on the network. Only the adapter vendor is known.',
      server: false,
    );
  }
  if (sameAdapter <= 1) return kind;
  return EngelAddressKind(
    label: kind.label,
    detail: '${kind.detail} Same adapter has $sameAdapter addresses.',
    server: kind.server,
  );
}
