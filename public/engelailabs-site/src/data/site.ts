export const navigation = [
  { label: "Engel AI Main", path: "/engel-ai-main" },
  { label: "About", path: "/about" },
  { label: "Technology", path: "/technology" },
  { label: "Platform", path: "/platform" },
  { label: "Apps", path: "/apps" },
  { label: "Agent", path: "/agents" },
  { label: "Genesis", path: "/genesis" },
  { label: "Community", path: "/community" },
] as const;

export const focusAreas = [
  {
    eyebrow: "Local intelligence",
    title: "AI that stays close",
    copy: "Personal AI foundations designed around local operation, data ownership, and deliberate boundaries.",
  },
  {
    eyebrow: "Coordinated systems",
    title: "Agents with a clear role",
    copy: "Purpose-built workflows route work across specialized capabilities while preserving visible control.",
  },
  {
    eyebrow: "Human authority",
    title: "Automation with a hand on the wheel",
    copy: "Verification, approval, and understandable system state keep people in charge of meaningful actions.",
  },
] as const;

export const aboutPrinciples = [
  ["Local AI", "Build useful intelligence around local models and user-owned context."],
  ["Agent systems", "Compose focused capabilities into workflows that remain understandable."],
  ["Device coordination", "Connect approved worker devices through bounded, explicit jobs."],
  ["Verification", "Treat evidence and review as part of the system, not an afterthought."],
  ["Privacy-focused workflows", "Minimize exposure and preserve clear public/private boundaries."],
] as const;

export const architecture = [
  { name: "Engel AI Main", note: "The personal AI command experience" },
  { name: "Engel Core", note: "Local intelligence and coordination foundation" },
  { name: "Agents", note: "Specialized, governed workflows" },
  { name: "Remote Workers", note: "Approved execution surfaces and connected devices" },
  { name: "Applications", note: "Independent products built around real needs" },
] as const;

export const localIntelligence = {
  reviewedOn: "August 25, 2026",
  summary:
    "Engel AI Main's local intelligence stack is a tokenizer, an embedding transformer, and a six-head advisory SLM roster. Deterministic gates stay in charge.",
  tokenizer: {
    name: "Local tokenizer",
    state: "Ready on the Engel AI Main server runtime",
    detail:
      "Uses the local Nomic Embed Text v1.5 tokenizer files. No Hugging Face Hub download at runtime. If those files are not loaded, Engel falls open to a local n-gram encoder.",
  },
  transformer: {
    name: "Local embedding transformer",
    state: "Ready on the Engel AI Main server runtime",
    detail:
      "The Nomic Embed Text v1.5 encoder turns text into features for the SLM roster. It runs on CPU, offline. Missing files fail open; they do not stop chat.",
  },
  slm: {
    name: "Advisory SLM roster",
    state: "Three heads serving, three not yet serving",
    detail:
      "Six small local classifiers. Serving behind gates: Intent Router, Style Checks, Training Admission. Reply Grader exists but is below its metric gate. Route Governor and Failure Triage are still collecting evidence and do not decide anything.",
  },
} as const;

export const platformCapabilities = [
  { name: "Engel AI Main", copy: "The current Windows workspace. Daily side: Chat, Discord, Status, Settings, and Advanced. Search finds every other tool." },
  { name: "Agent routing", copy: "Directs requests toward focused capabilities and tools." },
  { name: "Memory Guard", copy: "Maintains boundaries between context, candidates, and trusted knowledge." },
  { name: "Verification", copy: "Makes checks, evidence, and review visible in the workflow." },
  { name: "Device Swarm", copy: "Coordinates multiple approved devices as one understandable system." },
  { name: "Remote Workers", copy: "Extends bounded jobs to connected worker surfaces." },
] as const;

export const rustRewrite = {
  title: "Engel Core Rust rewrite",
  initialWindow: "May 31–June 2, 2026",
  continuedThrough: "Continued hardening through July 30, 2026",
  summary:
    "A focused rewrite moved Engel Core from a predominantly Python-backed route surface to a Rust-native coordination foundation, then continued through integration and hardening work.",
  durationEvidence: [
    {
      value: "40+ hours",
      label: "Operator-reported build effort",
      note: "The recorded 37-hour core migration plus the following integration slices support this total.",
    },
    {
      value: "53h 29m",
      label: "Receipt campaign",
      note: "Elapsed from the first feature inventory through the final retained live-cutover verification.",
    },
    {
      value: "64h 44m",
      label: "Source-provenance window",
      note: "Elapsed from the first source appearance through the last newly created initial module.",
    },
  ],
  completionEvidence: [
    { value: "492 / 492", label: "Route features Rust-native", note: "June 1 migration inventory" },
    { value: "517", label: "Native routes", note: "June 2 completion report" },
    { value: "264 / 0", label: "Rust tests passed / failed", note: "June 2 completion report" },
    { value: "260", label: "Workflow steps passed", note: "June 2 full workflow" },
  ],
  currentScale: [
    { value: "47 + build.rs", label: "Source modules" },
    { value: "3.54 MB", label: "Authored Rust" },
    { value: "~90k", label: "Physical lines" },
    { value: "286", label: "Inline test markers" },
  ],
  provenanceNote:
    "These durations describe retained evidence windows, not continuous hands-on labor. The Rust source tree was untracked by Git during the rewrite, so provenance comes from source timestamps, migration inventories, workflow receipts, completion reports, and project records rather than commits.",
  currentStateNote:
    "The latest retained records document continued work through July 30 and preserve intentional service-lane exceptions. This is a historical, evidence-backed snapshot—not a freshly rerun live audit and not a claim that every Engel ecosystem component is written in Rust.",
} as const;

export const engelMain = {
  name: "Engel AI Main",
  version: "1.1.0+2",
  platform: "Windows desktop",
  state: "Current local build",
  summary:
    "Engel AI Main is the local Windows workspace. The daily side is Chat, Discord, Status, Settings, and Advanced. Search still finds every other tool.",
  availability:
    "Chat, Discord, models, phones, and training depend on the local runtime and on connections you approve. This public site shows the product surface. It does not connect to or control the desktop app.",
  sourceUrl: "https://github.com/engelstands-hue/engel-ai-main",
  xUrl: "https://x.com/engelaimain",
  chatRouteLabel: "Auto Best",
  quickActions: [
    ["Attach", "Add a file to the message you are about to send."],
    ["Folder", "Point Engel at a working folder."],
    ["Send", "The message stays in the chat until the header says Chat ready."],
  ],
  dailyDesks: [
    {
      name: "Chat",
      role: "Talk with Engel",
      copy: "The center of the window. The header shows Chat ready when the local chat service answers, and the route chip shows the selected chat path. The current build labels that path Auto Best. Attach a file or open a folder, then send.",
      views: ["Chat ready", "Auto Best", "Attach", "Folder"],
    },
    {
      name: "Discord",
      role: "House desks",
      copy: "Engel house desks live here: Research, Product, Community, Support, Sales, Ops, Architect, Memory, Builder, Proof, and Training. Discord is chat. It does not control the desktop app.",
      views: ["Research", "Product", "Ops", "Training"],
    },
    {
      name: "Status",
      role: "See what is answering",
      copy: "Check whether chat and the local stack are answering. A quiet desk is shown as quiet.",
      views: ["Status"],
    },
    {
      name: "Settings",
      role: "Everyday controls",
      copy: "Models, connections and API keys, appearance, memory, and devices. Advanced tools stay one tap away.",
      views: ["Models", "Connections", "Appearance", "Memory", "Devices"],
    },
    {
      name: "Advanced",
      role: "Everything else",
      copy: "Devices, work, brain, and build tools open from here. Reference items are labeled and do not run tools. The search box still finds every desk.",
      views: ["Devices", "Work", "Brain", "Build", "Reference"],
    },
  ],
  advancedGroups: [
    {
      name: "Devices",
      copy: "Phones, connection help, the swarm view, Sub-Engel, and worker dispatch.",
      views: ["Devices / phones", "Connection Help", "Swarm 3D", "Sub-Engel", "Worker Dispatch"],
    },
    {
      name: "Work",
      copy: "Tasks, the Meeting Room, agents, and goals.",
      views: ["Tasks", "Meeting Room", "Agents", "Goals"],
    },
    {
      name: "Brain",
      copy: "Wiki, notes, memory, models, training, and the RAG lab.",
      views: ["Wiki One", "Notes", "Memory", "Models", "Training", "RAG Lab"],
    },
    {
      name: "Build",
      copy: "Build, proof, system, terminal, artifacts, and the older home screen.",
      views: ["Build", "Proof", "System", "Terminal", "Artifacts", "Legacy Home"],
    },
    {
      name: "Reference",
      copy: "Diagrams, learning cards, and a glossary. These do not run tools.",
      views: ["Agent Loops", "Nmap Recon", "AI Terms"],
    },
  ],
  workFlow: [
    ["01", "Human intent", "A person starts the request and remains the authority for meaningful actions."],
    ["02", "Visible routing", "Engel selects an available model, tool, agent, or worker lane and shows the chosen path."],
    ["03", "Bounded work", "The selected local or approved connected capability performs only the scoped job."],
    ["04", "Proof and review", "Results return with state, receipts, or evidence so the person can inspect what happened."],
  ],
} as const;

export const products = [
  {
    name: "Engel Discord House",
    type: "Current",
    copy: "The Engel desks: Research, Product, Community, Support, Sales, Ops, Architect, Memory, Builder, Proof, and Training. Each one speaks as itself. Discord is chat. It does not control the desktop app.",
  },
  {
    name: "Engel Remote Worker",
    type: "Current",
    copy: "The Android app on the worker phones. It shows who the phone is, which agent is assigned, and the message transcript. Phones do not run Discord.",
  },
  {
    name: "Agent Meeting Room",
    type: "Current",
    copy: "Assemble agents and send a job. Local Engel keeps a record. An Android worker can take a real job. A Sub-Engel job stays a preview.",
  },
  {
    name: "Sub-Engel",
    type: "Current",
    copy: "A second Windows computer that can check in with Engel AI Main. Work sent there is preview only.",
  },
  {
    name: "BC Rally",
    type: "Current",
    copy: "The BAD COMPANY clan voice for DayZ. It keeps its own persona in the gaming room. It is not one of the Engel AI Main desks.",
  },
  {
    name: "Swarm 3D",
    type: "Current",
    copy: "A three-dimensional view of the connected workers. It opens from Advanced, under Devices.",
  },
  {
    name: "Wiki One",
    type: "Current",
    copy: "The second brain inside Engel AI Main. It keeps the organ map, duties, and the journal on the machine.",
  },
  {
    name: "Engel Code Companion",
    type: "Current",
    copy: "Review-only help for reading code and proposing a change. It does not apply a patch by itself.",
  },
  {
    name: "Engel Bible Companion",
    type: "Independent",
    copy: "A standalone product for thoughtful Bible study and companionship. It is not the Engel AI core or platform runtime.",
  },
  {
    name: "Engel Swarm",
    type: "Portfolio concept",
    copy: "A product concept for organizing connected agents and worker capabilities.",
  },
  {
    name: "Engel 1000 Agent Trainer",
    type: "Portfolio concept",
    copy: "A focused environment for preparing and evaluating large agent rosters.",
  },
  {
    name: "JD Roadside Assistance",
    type: "Portfolio concept",
    copy: "A practical roadside workflow product designed around timely, clear assistance.",
  },
  {
    name: "JD Roadside Receipts",
    type: "Portfolio concept",
    copy: "A companion product for clear, organized roadside service receipts.",
  },
  {
    name: "FarmLife Writer",
    type: "Portfolio concept",
    copy: "A writing product shaped for rural stories, records, and everyday creative work.",
  },
] as const;

export const builtHere = [
  {
    label: "Dev templates for Obsidian and Notion",
    url: "https://forge.engelailabs.com/?utm_source=engelailabs&utm_medium=homepage",
  },
  {
    label: "VIBE // DROP — vibe-coding tees",
    url: "https://wearthecrash.printful.me/?utm_source=engelailabs&utm_medium=homepage",
  },
] as const;

export const genesisTimeline = [
  { era: "Genesis 01", title: "First Engel interface", copy: "The first visible place for a person and Engel to work together.", featured: false },
  { era: "Genesis 02", title: "First local AI experiments", copy: "Early exploration of useful intelligence running close to the user.", featured: false },
  {
    era: "Genesis 03 · May 31–June 2, 2026",
    title: rustRewrite.title,
    copy: "A 40+ hour, receipt-backed migration moved the original route surface into a Rust-native core. Integration and hardening continued through July 30.",
    featured: true,
  },
  { era: "Genesis 04", title: "Server expansion", copy: "The system grew beyond one surface into a broader computing foundation.", featured: false },
  { era: "Genesis 05", title: "Worker devices", copy: "Dedicated devices introduced new ways to carry out bounded work.", featured: false },
  { era: "Genesis 06", title: "Device swarm", copy: "Independent workers began to form one coordinated, human-readable whole.", featured: false },
  { era: "Genesis 07", title: "Platform evolution", copy: "The pieces converged into the Engel AI Labs technology ecosystem.", featured: false },
] as const;

export const placeholders = [
  { path: "/api", title: "Public API", copy: "Reserved for a future, purpose-built public API. No service or private system is connected." },
  { path: "/auth", title: "Identity", copy: "Reserved for future public account access. No authentication provider is configured." },
  { path: "/workers", title: "Worker portal", copy: "Reserved for future public worker documentation. No devices are discovered, contacted, or controlled." },
] as const;

export const ambassador = {
  name: "Engel AI Ambassador",
  handle: "engel-ai-main",
  profileUrl: "https://www.moltbook.com/u/engel-ai-main",
  launchPostTitle: "Building Engel AI in public",
  launchPostUrl: "https://www.moltbook.com/post/86ab2617-e6d2-4019-ba78-346635dd7298",
  confirmedPostCount: 2,
  reviewedOn: "August 14, 2026",
  authorizationRequirement: "Written Moltbook authorization",
  communityParticipation: {
    status: "Human-reviewed",
    scope: "Relevant public discussions selected by a person",
    readiness: "The local review console can perform one explicit, bounded discovery and prepare one exact draft for a person's decision.",
    membership: "No live Submolt membership is claimed until a successful Moltbook subscription response is recorded.",
    inactivity: "No recurring discovery, subscription, post, or comment automation is active; each review and send is a separate human action.",
  },
  automationProfiles: {
    first24Hours: {
      posts: "At most one post every 2 hours",
      comments: "At most one comment every 60 seconds and 20 comments per day",
    },
    established: {
      posts: "At most one post every 30 minutes",
      comments: "At most one comment every 20 seconds and 50 comments per day",
    },
    platformCeilings: {
      reads: "60 reads per minute",
      writes: "30 writes per minute",
    },
    verification: "Challenges expire after 5 minutes; 10 consecutive failures or expirations can suspend the account.",
  },
} as const;
