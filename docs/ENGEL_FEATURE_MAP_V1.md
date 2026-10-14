# Engel AI Main feature map

This is the user-facing map every provider lane reads before driving a surface. It covers Engel AI Main and the parts around it. Internals stay out of this file. A missing section means the run stops.

Provider setup pages, social sites, and other web pages open in the Engel browser inside the Engel AI Main window. An outside browser is not used for those pages.

Authority stays Josh, then Guardian, then Engel. This map does not start a loop, post to Slack, or merge a branch.

### Engel AI Main desktop chat

The main window where a person talks to Engel on this computer.

#### How a user gets there

- Launch Engel AI Main desktop. The window is four panels: System Monitor, Agent Chat, the Goals Models Routes tabs, and the status bar.
- Type a phrase in Agent Chat. No keyboard shortcut.

#### How the control adapter drives it

- A browser adapter cannot drive this Qt window. Status: blocked.
- A person types the phrase and reads the reply in Agent Chat.
- Reset by starting a new chat turn. Do not clear memory from this map.

#### Stable selectors

- Window title Engel AI Main
- Panel Agent Chat
- Tabs Goals, Models, Routes

#### States to exercise

- Default, empty chat, a answered phrase, error
- Hover and focus-visible do not apply to the Qt panels the same way as a web page

#### Preconditions and setup

- Auth: the person at this computer
- Data: local Engel files
- Permissions: Josh for any action that changes the live body
- Flags: none
- Services: desktop app open

#### Evidence and cross-check

- Screenshot: desktop window with the phrase and the reply
- Video: type the phrase and show the reply
- Cross-check: the same phrase through the local ask command returns the same route

#### Gotchas

- Meeting Room phrases are intercepted in this chat before a provider sees them.
- The public website is a different surface.

### Engel AI Main one-system chat

The server face of Engel AI Main on this computer.

#### How a user gets there

- Open the Engel AI Main one-system page from the desktop shortcut or the local chat address on this computer.
- No keyboard shortcut.

#### How the control adapter drives it

- Open the local chat page, type in the message box, and send. The reply should appear in the thread.
- Reset by leaving the draft message empty.
- If the page does not load, the run is blocked.

#### Stable selectors

- Page titled as Engel AI Main chat
- Message box and send control on that page

#### States to exercise

- Default, empty, loading, error, a sent message

#### Preconditions and setup

- Auth: the person at this computer
- Data: none beyond the typed phrase
- Permissions: Josh for actions
- Flags: none
- Services: the one-system chat is up

#### Evidence and cross-check

- Screenshot: the typed phrase and the reply
- Video: send one phrase
- Cross-check: the reply names the route or the answer, not a second app

#### Gotchas

- The public website is not this chat.
- Do not use a house network address in a public note.

### Agent Meeting Room

The room where an order from Engel AI Main is handed to a desk.

#### How a user gets there

- From Engel AI Main chat, ask for the meeting room. The room window has no prompt of its own.
- No keyboard shortcut.

#### How the control adapter drives it

- Browser control cannot drive the Qt room. Status: blocked.
- A person sends the order from the main chat and reads the room result there.
- Reset by leaving the room without filing another order.

#### Stable selectors

- Window title Meeting Room
- Order text that arrived from the main chat

#### States to exercise

- Empty room, one open order, a completed reply, error

#### Preconditions and setup

- Auth: the person at this computer
- Data: one order sentence
- Permissions: Josh
- Flags: none
- Services: Meeting Room window

#### Evidence and cross-check

- Screenshot: the order and the room result
- Video: send one order from the main chat
- Cross-check: the result names the order, not a phone command

#### Gotchas

- The text-only meeting routes are a different surface from this window.
- Phone workers do not take Discord from this room.

### Discord house

The shared Engel AI Labs chats led by Engel AI Main.

#### How a user gets there

- Open Discord in the Engel browser inside Engel AI Main, then Engel AI Labs, #general or Bot Talk.
- No keyboard shortcut.

#### How the control adapter drives it

- Do not post as a bot from this map. Status: blocked for posting.
- A person may read #general.
- Reset is not required because this map does not send a message.

#### Stable selectors

- Server Engel AI Labs
- Channel general
- Channel Bot Talk

#### States to exercise

- Quiet channel, a finished-work post, a withheld empty-status line

#### Preconditions and setup

- Auth: a person already in the server
- Data: none
- Permissions: read
- Flags: none
- Services: Discord mouths on the Engel server

#### Evidence and cross-check

- Screenshot: #general showing a finished result, or staying quiet when there is no result
- Video: not required while posting is blocked
- Cross-check: a desk with nothing new does not add "nothing is queued" or "collab if this helps"

#### Gotchas

- Desk rooms are a different surface.
- Empty status scripts are not work and stay off the channel.
- Every Discord bot is a conical part of Engel AI Main.
- Engel is Engel AI Main's own phone inside the Engel window. The mouths explain that phone. They do not send it to Alpha, Beta, or Gamma.
- Alpha, Beta, and Gamma are resources for the bot workers. Research, Product, Architect, and Training use Alpha. Support, Ops, and Builder use Beta. Community, Sales, Memory, and Proof use Gamma.

### Discord desk rooms

Each desk speaks in its own room.

#### How a user gets there

- Open Discord in the Engel browser inside Engel AI Main, then the desk category for research, product, community, support, sales, or ops.
- Architect, Memory, Builder, Proof, and Training are mouths that report to Engel AI Main.
- No keyboard shortcut.

#### How the control adapter drives it

- Posting is blocked. A person reads the desk room.
- Reset is not required.

#### Stable selectors

- Channels named for research, product, community, support, sales, and ops

#### States to exercise

- Quiet, a board post that lists titles, a service-down note, error

#### Preconditions and setup

- Auth: a person in the server
- Data: none
- Permissions: read
- Flags: none
- Services: that desk mouth

#### Evidence and cross-check

- Screenshot: the desk room
- Video: not required while posting is blocked
- Cross-check: a competition or credit board appears only when it has titles

#### Gotchas

- #general is the house surface, not the desk room.
- Discord stays off the phones.

### Android workers

Three phones, each with its own worker.

#### How a user gets there

- Unlock the assigned phone and open the Engel remote worker app.
- Alpha carries research, product, architect, and training.
- Beta carries support, ops, and builder.
- Gamma carries community, sales, memory, and proof.
- No keyboard shortcut.

#### How the control adapter drives it

- This computer's browser cannot drive the phone UI. Status: blocked.
- A person reads the identity badge, the assigned agent, and the message transcript on the phone.
- Reset by leaving the app in the foreground without sending a new job.

#### Stable selectors

- App identity badge
- Assigned agent chip
- Message transcript

#### States to exercise

- App open, no job, one queued job, error

#### Preconditions and setup

- Auth: the phone is unlocked by the person
- Data: the desk sandbox on that phone
- Permissions: Josh before a new job
- Flags: none
- Services: the phone app

#### Evidence and cross-check

- Screenshot: the phone app showing the worker name
- Video: open the app
- Cross-check: the desk name on the phone matches the lane above

#### Gotchas

- Do not put a phone serial in a public note.
- Discord is not on the phone.

### Public website

The public page for Engel AI Labs.

#### How a user gets there

- Open https://engelailabs.com in the Engel browser inside Engel AI Main
- Open https://engelailabs.com/engel-ai-main for the product page in that same browser
- No keyboard shortcut

#### How the control adapter drives it

- Open the product page. Click `Read the source`. The GitHub repository should open.
- Reset by returning to the product page.

#### Stable selectors

- Link `Read the source`
- Footer link `Source`
- Footer link `X`

#### States to exercise

- Default, the product page, the source link opened

#### Preconditions and setup

- Auth: none
- Data: none
- Permissions: public read
- Flags: none
- Services: the public site

#### Evidence and cross-check

- Screenshot: product page with `Read the source`
- Video: click `Read the source`
- Cross-check: the link target is https://github.com/engelstands-hue/engel-ai-main

#### Gotchas

- The Windows installer is not a public download.
- The local chat page is a different surface.

### Public source

The public source snapshot.

#### How a user gets there

- Open https://github.com/engelstands-hue/engel-ai-main
- Default branch is `main`
- No keyboard shortcut

#### How the control adapter drives it

- Open the repository and read the file list. Do not push `main` from this map.
- Reset by leaving the branch selector on `main`.

#### Stable selectors

- Repository `engelstands-hue/engel-ai-main`
- Branch `main`

#### States to exercise

- Default branch, a draft pull request, an empty title refused

#### Preconditions and setup

- Auth: public read. Push only from a dispatched draft-pr phrase.
- Data: the snapshot tree
- Permissions: Josh before a push
- Flags: none
- Services: GitHub

#### Evidence and cross-check

- Screenshot: the repository home
- Video: open one file
- Cross-check: the default branch is `main`

#### Gotchas

- This snapshot is not the live Engel body and not the history remote.
- Do not publish secrets, phone serials, or house network addresses.

### Slack channel

Work notes stay in a private Slack channel. The workspace name, channel name, and channel id are not in this map.

#### How a user gets there

- Open the private Slack channel in the Engel browser inside Engel AI Main. The local Benny config holds the target.
- No keyboard shortcut.

#### How the control adapter drives it

- Reading the channel is allowed when Slack is signed in.
- Posting is not part of this map. Status: blocked for posts.
- Reset is not required.

#### Stable selectors

- Local Slack target, not published
- Public config value `slack_target: private-machine-only`

#### States to exercise

- Channel open, empty of agent posts, a person-written work note

#### Preconditions and setup

- Auth: a signed-in member
- Data: the private local Slack target
- Permissions: read
- Flags: none
- Services: Slack

#### Evidence and cross-check

- Screenshot: not published
- Video: not required while posting is blocked
- Cross-check: the public map has no workspace name, channel name, or channel id

#### Gotchas

- Do not publish the workspace name, channel name, or channel id.
- Benny does not post here unless a later dispatch says to post.

### Public X account

The public Engel AI Main account.

#### How a user gets there

- Open https://x.com/engelaimain in the Engel browser inside Engel AI Main
- No keyboard shortcut

#### How the control adapter drives it

- Open the profile and read the latest post.
- Posting a new item is blocked unless Josh asks in that turn.
- Reset by not typing in the composer.

#### Stable selectors

- Profile `engelaimain`

#### States to exercise

- Profile loaded, one existing post visible

#### Preconditions and setup

- Auth: public read
- Data: none
- Permissions: public read
- Flags: none
- Services: X

#### Evidence and cross-check

- Screenshot: the profile header
- Video: open the profile
- Cross-check: the profile link is https://x.com/engelaimain

#### Gotchas

- Do not post as any other account.

### Saved skills and Pstack

The skill list and the three Pstack agents.

#### How a user gets there

- In Engel AI Main chat, say `saved skills`.
- No keyboard shortcut.

#### How the control adapter drives it

- Browser control does not apply. A person uses the chat phrase.
- The reply lists saved skills, including the `pstack-` set.
- Reset is a new phrase.

#### Stable selectors

- Phrase `saved skills`
- Agent names Engel Pstack Poteto, Engel Pstack Comment Sicko, Engel Pstack Benny

#### States to exercise

- List shown, a missing registry reported as an error

#### Preconditions and setup

- Auth: the person at this computer
- Data: the saved skill registry
- Permissions: read
- Flags: none
- Services: local Engel

#### Evidence and cross-check

- Screenshot: the skill reply
- Video: send `saved skills`
- Cross-check: Benny's skill list includes triage, reproduce, and setup

#### Gotchas

- Pstack principle text does not override Josh or Guardian.
- Poteto and Comment Sicko do not open pull requests.

### Architect founder gate

The plan gate that waits for Josh.

#### How a user gets there

- Ask Engel for the architect status in chat.
- No keyboard shortcut.

#### How the control adapter drives it

- Browser control does not apply.
- A person reads whether a plan is waiting at the founder gate.
- Reset by not approving anything from this map.

#### Stable selectors

- Phrase that asks for architect status

#### States to exercise

- No plan waiting, a plan waiting, error

#### Preconditions and setup

- Auth: Josh to pass the gate
- Data: the architect plan folder
- Permissions: read for status, Josh for approval
- Flags: none
- Services: local Engel

#### Evidence and cross-check

- Screenshot: the status reply
- Video: ask once
- Cross-check: the reply does not say a plan was approved unless Josh approved it

#### Gotchas

- An empty plan folder is a status, not a chat script for Discord.

### Feature map

This document.

#### How a user gets there

- In Engel AI Main chat, say `feature map`.
- Add a section name to read one part, for example `feature map Discord house`.
- No keyboard shortcut.

#### How the control adapter drives it

- A person uses the chat phrase.
- The reply lists every section, or the one named section.
- Reset by asking for `feature map` with no section name.

#### Stable selectors

- Phrase `feature map`
- File `docs/ENGEL_FEATURE_MAP_V1.md`

#### States to exercise

- Full index, one section, an unknown section name

#### Preconditions and setup

- Auth: read
- Data: this file
- Permissions: read
- Flags: none
- Services: local Engel

#### Evidence and cross-check

- Screenshot: the section list
- Video: ask `feature map`
- Cross-check: every section in this file has a user path, adapter actions, and a reset

#### Gotchas

- The example map inside the Pstack pack is not this file. Do not edit that example.

### Draft pull request

Opens a draft pull request on the public source repository.

#### How a user gets there

- In Engel AI Main chat, say `open draft pr` plus a title.
- Example: `open draft pr Add the Engel feature map`
- No keyboard shortcut.

#### How the control adapter drives it

- The phrase is the dispatch. The bot creates branch `collab/<date>-<slug>` on https://github.com/engelstands-hue/engel-ai-main and opens a draft pull request.
- Reset is not automatic. Closing the draft is a separate GitHub action by Josh.
- An empty title does not open a pull request.

#### Stable selectors

- Phrase `open draft pr`
- Repository `engelstands-hue/engel-ai-main`
- Draft badge on the pull request

#### States to exercise

- Usage with no title, a draft opened, a refusal to push `main`

#### Preconditions and setup

- Auth: the GitHub account `engelstands-hue` on this computer
- Data: the public snapshot
- Permissions: Josh dispatched the phrase
- Flags: draft only
- Services: GitHub

#### Evidence and cross-check

- Screenshot: the draft pull request page
- Video: not required when the reply includes the pull request URL
- Cross-check: the base branch is `main`, the head is `collab/...`, and the pull request is a draft

#### Gotchas

- This does not merge.
- This does not push `main`.
- This does not copy the change into the live server.
- Poteto and Comment Sicko do not use this phrase.

### Cosmic Swarm console

The operator console for the rest of Engel AI Main: daily Chat, Status, and Settings, plus the Advanced desks.

#### How a user gets there

- Launch the Engel AI Main operator console.
- Use the daily row: Chat, Status, Settings.
- Open Advanced for Notes, Tasks, Models, Training, Devices, System, Proof, Agents, Goals, Memory, and Build.
- On Devices, open Swarm 3D. Every audited LAN and WiFi device is a node on the map. Tap a node to read what it is and where it is. Set place records the room. Open server chat and Open meeting room use the tunnels already on this PC. View phone opens that worker. Scan network stays a button you press.
- No keyboard shortcut.

#### How the control adapter drives it

- A browser adapter cannot drive this window. Status: blocked.
- A person opens one daily tab or one Advanced desk and reads that page.
- Reset by returning to Chat.

#### Stable selectors

- Tabs Chat, Status, Settings
- Advanced desks Notes, Tasks, Models, Training, Devices, System, Proof, Agents, Goals, Memory, Build
- Button View phone on the selected Swarm 3D device
- Button Open server chat
- Button Open meeting room
- Button Set place

#### States to exercise

- Chat landing, Status open, Settings open, one Advanced desk, error

#### Preconditions and setup

- Auth: the person at this computer
- Data: local Engel records for the desk being opened
- Permissions: read. Josh before a change
- Flags: none
- Services: the operator console

#### Evidence and cross-check

- Screenshot: the open tab name
- Video: open Status, then return to Chat
- Cross-check: the tab name matches the desk

#### Gotchas

- The four-panel desktop chat is a different window.
- Swarm 3D does not scan the network by itself. Scan network is the button that looks.
- Settings must not show a saved key.

### Control Room

The window that shows whether the one system, the Meeting Room, Discord, and the phones are up.

#### How a user gets there

- Launch the Engel Control Room.
- No keyboard shortcut.

#### How the control adapter drives it

- Browser control cannot drive this window. Status: blocked.
- A person reads the status rows.
- Reset by closing the window. Do not start a service from this map.

#### Stable selectors

- Window title Control Room
- Status rows for chat, Meeting Room, Discord, and the phones

#### States to exercise

- Rows visible, one row unavailable, error

#### Preconditions and setup

- Auth: the person at this computer
- Data: live status probes
- Permissions: read
- Flags: none
- Services: Control Room window

#### Evidence and cross-check

- Screenshot: the status rows
- Video: open the window
- Cross-check: a phone row names Alpha, Beta, or Gamma, not a serial

#### Gotchas

- Control Room is a face. It is not a second Engel body.
- Do not put a house network address in a public note.

### Wiki One

The living map of Engel AI Main.

#### How a user gets there

- In Engel AI Main chat, say `wiki one`.
- No keyboard shortcut.

#### How the control adapter drives it

- A person uses the chat phrase.
- The reply shows the body map.
- Reset by asking `wiki one` again.

#### Stable selectors

- Phrase `wiki one`

#### States to exercise

- Map shown, journal shown, error

#### Preconditions and setup

- Auth: read
- Data: the Wiki One file
- Permissions: read. A duty change is a separate job
- Flags: none
- Services: local Engel

#### Evidence and cross-check

- Screenshot: the wiki reply
- Video: say `wiki one`
- Cross-check: the reply names organs, not a secret

#### Gotchas

- Wiki One is not the Notes desk.
- Updating the wiki is not the same phrase as reading it.

### REPS

The improvement loop: Record, Evaluate, Propose, Sign-off.

#### How a user gets there

- Read the REPS note for the job Engel just finished.
- No keyboard shortcut.

#### How the control adapter drives it

- Browser control does not apply.
- A person reads the record, the score, the proposal, and who must sign.
- Reset by leaving the note unchanged.

#### Stable selectors

- Labels Record, Evaluate, Propose, Sign-off

#### States to exercise

- A record present, a proposal waiting, sign-off still with Josh

#### Preconditions and setup

- Auth: Josh for sign-off
- Data: the job note
- Permissions: read
- Flags: none
- Services: local Engel records

#### Evidence and cross-check

- Screenshot: the four labels
- Video: open one note
- Cross-check: sign-off is still Josh's

#### Gotchas

- A REPS note does not apply a change by itself.
- This is not a provider call.

### Graph and Loop Studio

The engineering graph window beside Engel.

#### How a user gets there

- In Engel AI Main chat, say `open graph studio`.
- No keyboard shortcut.

#### How the control adapter drives it

- Browser control does not apply.
- A person opens the studio and reads the graph list.
- Reset by closing the studio. Do not create a graph from this map.

#### Stable selectors

- Phrase `open graph studio`
- Phrase `graph studio list`

#### States to exercise

- Studio closed, studio open, list empty, list with one graph

#### Preconditions and setup

- Auth: the person at this computer
- Data: saved graphs, if any
- Permissions: read to list. Josh before a new graph
- Flags: none
- Services: Graph and Loop Studio

#### Evidence and cross-check

- Screenshot: the studio window or the list reply
- Video: say `open graph studio`
- Cross-check: the studio is an Engel part, not a second body

#### Gotchas

- `new engel graph` creates a graph. This map only opens and lists.

### Sub-Engel

The paired nest a guest reaches by addressing Sub-Engel.

#### How a user gets there

- In Discord, address Sub-Engel in a room where guests may speak.
- No keyboard shortcut.

#### How the control adapter drives it

- Posting is blocked. A person reads the Sub-Engel reply.
- Reset is not required.

#### Stable selectors

- Name Sub-Engel

#### States to exercise

- Silent unless addressed, a reply when addressed, roll call

#### Preconditions and setup

- Auth: a person in the Discord server
- Data: the message that addresses Sub-Engel
- Permissions: read
- Flags: none
- Services: the Sub-Engel mouth

#### Evidence and cross-check

- Screenshot: a reply that starts only after Sub-Engel was addressed
- Video: not required while posting is blocked
- Cross-check: Engel AI Main does not answer as Sub-Engel

#### Gotchas

- This computer is not Sub-Engel.
- Do not put a machine name or a network address in a public note.

### Verifiers

The local proof Engel runs before a job is called done.

#### How a user gets there

- Ask for the verifier that matches the files just changed.
- No keyboard shortcut.

#### How the control adapter drives it

- Browser control does not apply.
- A person runs the named verifier and reads pass or fail.
- Reset by leaving the source unchanged after a failure.

#### Stable selectors

- Verifier name printed at the end of the run
- Phrase `feature map` still returns the section index after this map changes

#### States to exercise

- Pass, fail, a missing verifier file

#### Preconditions and setup

- Auth: the person at this computer
- Data: the files under test
- Permissions: read and run a local verifier
- Flags: none
- Services: the local Python Engel owns

#### Evidence and cross-check

- Screenshot: the pass line
- Video: run one verifier
- Cross-check: a fail lists the check name

#### Gotchas

- A screenshot is not a pass.
- The full sweep is longer than one feature-map check.

### Engel browser

The browser inside the Engel AI Main window. Provider setup pages, social sites, and other web pages open here.

#### How a user gets there

- Open Engel AI Main, then the Browser icon on the side ribbon.
- Open a provider or social from Connections, chat, or a setup button. The page opens in this browser.
- No keyboard shortcut. F12 opens developer tools while this browser is focused.
- The page rests when the Engel window is not in front, so the graphics chip can idle.

#### How the control adapter drives it

- Use the address field, tabs, and the Browser options menu.
- Engel is Engel AI Main's own phone. Its home and apps run in this window. A separate phone program is not started.
- Alpha, Beta, and Gamma draw that phone's own screen inside this same window, including its home, apps, and store.
- Back, Home, and Recent apps use the phone's own buttons. Home shows that phone's home screen. Touch and the wheel act on the picture inside Engel.
- Browser options holds History, Settings, Developer tools, screenshot, hard reload, copy URL, the bookmark bar, and clear history, cookies, and cache.
- Reset by closing tabs until one blank tab remains.

#### Stable selectors

- Ribbon icon Browser
- Address field
- Button Browser options
- Tab close mark

#### States to exercise

- Blank tab, one open page, a second tab, History, Settings, developer tools, Engel phone home, a real app on that phone

#### Preconditions and setup

- Auth: the person at this computer, plus the site sign-in when a provider or social asks for one
- Data: pages the person chooses to open
- Permissions: Josh for any sign-in or post
- Flags: none
- Services: Engel AI Main window

#### Evidence and cross-check

- Screenshot: the page inside the Engel window, not a separate browser
- Video: open one provider or social page from Engel AI Main
- Cross-check: `feature map Engel browser` returns this section

#### Gotchas

- This is the browser every provider and social uses.
- A Qt window, a phone, and a local file folder are different surfaces.
- Posting from a social page stays blocked unless Josh asks in that turn.

### Engel phone

Engel's own phone inside the Engel AI Main window. Every part below runs in that window. A separate phone program is not started.

#### How a user gets there

- Open Engel AI Main, then Browser on the side ribbon, then the phone icon.
- In chat, say `open the phone` or `how do I use the phone`.
- Name one part, for example `open the calculator on the phone` or `how do I use messages on the phone`.
- No keyboard shortcut.

#### How the control adapter drives it

- Home shows the clock and every app, including Play Store. The dock is Browser, Phone, Messages, and Notes.
- Browser: type a web address and press Enter. Back returns to the earlier page, then home.
- Play Store: opens the real Google Play Store on the signed-in phone, in this same window.
- Phone: type a number and press call. The call goes out through the signed-in phone. History opens the call log. Back ends the call.
- Messages: New message, then a number and the message. The message goes out through the signed-in phone.
- Contacts: New contact saves a name and a number. Tap a contact to open Phone with that number.
- Notes: New note writes a title and the note. Back saves it.
- Files: shows only files kept on this phone. New file saves text there.
- Clock: the time, a stopwatch with Start, Stop, Lap, and Reset, and a timer with +1 min, -1 min, and Start.
- Calculator: digits, plus, minus, times, divide, Equals, C, and backspace.
- Settings: the phone is Engel, model Engel AI Main. The line chooses Alpha, Beta, or Gamma for calls, messages, and the Play Store. Clear removes the call log or the messages.
- Back leaves the current page. Home returns to the phone home. Recent apps lists what is open.
- Phones switches among Engel, Alpha, Beta, and Gamma without closing the window. Alpha, Beta, and Gamma draw the live screen of that phone.
- All phones starts with the phone plus. Each click adds one phone you choose. See smaller, See phones, and See larger change how big those phones are. Each phone has All and Phones. A tap on Alpha, Beta, or Gamma lands on that phone. If a phone says to tap Allow, that tap is on the phone itself. A page stays in this window.
- Reset by pressing Home.

#### Stable selectors

- Ribbon icon Browser
- Button Engel phone
- Button Phones
- Button All phones
- Button phone plus
- Button See phones
- Button Back
- Button Home
- Button Recent apps
- App Browser
- App Play Store
- App Phone
- App Messages
- App Contacts
- App Notes
- App Files
- App Clock
- App Calculator
- App Settings

#### States to exercise

- Phone home, one open app, Recent apps, Back to home, Phones list while a phone is open, Alpha or Beta or Gamma live screen, Play Store on the signed-in phone

#### Preconditions and setup

- Auth: the person at this computer
- Data: notes, messages, contacts, call log, and files kept on this phone
- Permissions: Josh for any sign-in on a page opened in the phone browser
- Flags: none
- Services: Engel AI Main window

#### Evidence and cross-check

- Screenshot: the phone home inside the Engel window
- Video: open one app from chat, for example the calculator
- Cross-check: `feature map Engel phone` returns this section

#### Gotchas

- Engel's phone is not a separate program.
- Alpha, Beta, and Gamma are the phones next to you. Their screens are the live phones, not Engel's own apps.
- A call and a message go out through the signed-in phone. A note and a file stay on this phone.
- Play Store installs apps on the signed-in phone.

## Completeness checklist

- Every user-facing part above has a section.
- Every section names a user path, adapter actions, and a reset.
- Selectors use visible names.
- No selector uses a generated class or a screen position.
- Auth, data, permissions, flags, and services are named.
- Screenshot, video, and cross-check are named.
- Wrong surfaces are listed.
- Web pages for providers and socials open in the Engel browser inside the Engel window.
- Browser driving is marked blocked where the surface is not a web page.
