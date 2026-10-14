import 'package:flutter_test/flutter_test.dart';
import 'package:engel_flutter_main/engel_swarm_address.dart';

void main() {
  test('known Engel hosts are labeled server, phone, or computer', () {
    expect(
      engelAddressKind(
        id: 'engel-spine-01',
        name: 'Engel spine',
        type: 'server',
        role: 'proxmox-host',
        classification: 'cluster_member',
        hardware: 'Dell PowerEdge',
      ).label,
      'Server',
    );
    expect(
      engelAddressKind(
        id: 'meeting-room-server',
        name: 'Meeting Room',
        type: 'server',
        role: 'meeting-room',
        classification: 'logical_runtime',
        hardware: '',
      ).server,
      isTrue,
    );
    expect(
      engelAddressKind(
        id: 'android_worker_alpha',
        name: 'Alpha',
        type: 'android',
        role: 'phone-worker',
        classification: 'cluster_member',
        hardware: 'phone',
      ).label,
      'Phone',
    );
    expect(
      engelAddressKind(
        id: 'engel-main-pc',
        name: 'Engel AI Main',
        type: 'windows',
        role: 'main-controller',
        classification: 'cluster_member',
        hardware: 'laptop',
      ).label,
      'Computer',
    );
  });

  test('a LAN address is a television, a Windows computer, or not identified', () {
    expect(
      engelAddressKind(
        id: 'lan-candidate-tv',
        name: 'Living room TV',
        type: 'network',
        role: 'unassigned',
        classification: 'lan_candidate',
        hardware: 'Roku television',
      ).label,
      'Television',
    );
    expect(
      engelAddressKind(
        id: 'lan-candidate-pc',
        name: 'Unassigned Windows device',
        type: 'network',
        role: 'unassigned',
        classification: 'lan_candidate',
        hardware: 'Windows-class device',
      ).label,
      'Windows computer',
    );
    final unknown = engelAddressKind(
      id: 'lan-candidate-unknown',
      name: 'Unassigned LAN device',
      type: 'network',
      role: 'unassigned',
      classification: 'lan_candidate',
      hardware: 'Network adapter vendor: Unknown OUI',
      sameAdapter: 3,
    );
    expect(unknown.server, isFalse);
    expect(unknown.label, 'Not identified');
    expect(unknown.detail, contains('3 addresses'));
  });

  test('a device says what it is, where it is, and which reach action it has', () {
    final server = engelDeviceReach(
      id: 'engel-spine-01',
      name: 'Engel spine',
      hardware: 'Dell PowerEdge',
      physicalLocation: 'Physical Dell PowerEdge server; exact rack/room not assigned',
      kindLabel: 'Server',
      kindDetail: 'Dell PowerEdge host.',
    );
    expect(server.what, contains('Dell PowerEdge'));
    expect(server.where, 'Physical Dell PowerEdge server. Room not set.');
    expect(server.actions.map((action) => action.id), contains('open-chat'));
    expect(server.actions.map((action) => action.id), contains('open-meeting'));

    final phone = engelDeviceReach(
      id: 'android_worker_alpha',
      name: 'Alpha',
      hardware: 'motorola phone',
      physicalLocation: 'Attached to this PC',
      kindLabel: 'Phone',
      kindDetail: 'Engel phone worker.',
      placeOverride: 'Desk',
    );
    expect(phone.where, 'Desk');
    expect(phone.actions.map((action) => action.label), contains('View phone'));

    expect(engelSwarmShortName(id: 'local-llm-runtime', name: 'long runtime name', kindLabel: 'Server'), 'CT246');
    expect(engelNetbiosName('OFFICE-PC        <00>  UNIQUE      Registered'), 'OFFICE-PC');
  });
}
