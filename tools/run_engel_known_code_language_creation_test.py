#!/usr/bin/env python3
"""Create and validate Engel artifacts across a known code-language matrix."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_BASE = ROOT / "artifacts" / "engel_ui_results" / "multi_language_creation"
REPORT_DIR = ROOT / "reports" / "codex_bridge"


@dataclass(frozen=True)
class LanguageSpec:
    key: str
    display: str
    files: dict[str, str]
    validate: Callable[[Path], dict[str, Any]]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def tail(text: str, limit: int = 4000) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[-limit:]


def which_any(*names: str) -> str:
    for name in names:
        for path in candidate_tool_paths(name):
            if path.is_file():
                return str(path)
        found = shutil.which(name)
        if found:
            return found
    return ""


def candidate_tool_paths(name: str) -> list[Path]:
    home = Path.home()
    runtime_tools = ROOT / "runtime" / "toolchains"
    glob_patterns = {
        "tsc": [
            runtime_tools / "npm" / "node_modules" / ".bin" / "tsc.cmd",
            home / "AppData" / "Roaming" / "npm" / "tsc.cmd",
            Path("D:/npm-global/tsc.cmd"),
        ],
        "bash": [
            Path("C:/msys64/usr/bin/bash.exe"),
            Path("C:/Program Files/Git/bin/bash.exe"),
            Path("C:/Program Files/Git/usr/bin/bash.exe"),
            runtime_tools / "PortableGit" / "bin" / "bash.exe",
            runtime_tools / "msys64" / "usr" / "bin" / "bash.exe",
        ],
        "go": [
            Path("C:/Program Files/Go/bin/go.exe"),
            runtime_tools / "go" / "bin" / "go.exe",
        ],
        "gcc": [
            Path("C:/msys64/ucrt64/bin/gcc.exe"),
            Path("C:/msys64/mingw64/bin/gcc.exe"),
            Path("C:/Program Files/LLVM/bin/clang.exe"),
            runtime_tools / "llvm" / "bin" / "clang.exe",
        ],
        "g++": [
            Path("C:/msys64/ucrt64/bin/g++.exe"),
            Path("C:/msys64/mingw64/bin/g++.exe"),
            Path("C:/Program Files/LLVM/bin/clang++.exe"),
            runtime_tools / "llvm" / "bin" / "clang++.exe",
        ],
        "clang": [
            Path("C:/Program Files/LLVM/bin/clang.exe"),
            runtime_tools / "llvm" / "bin" / "clang.exe",
        ],
        "clang++": [
            Path("C:/Program Files/LLVM/bin/clang++.exe"),
            runtime_tools / "llvm" / "bin" / "clang++.exe",
        ],
        "dotnet": [
            runtime_tools / "dotnet" / "dotnet.exe",
            Path("C:/Program Files/dotnet/dotnet.exe"),
        ],
        "kotlinc": [
            Path("C:/Program Files/Kotlin/kotlinc/bin/kotlinc.bat"),
            runtime_tools / "kotlin" / "kotlinc" / "bin" / "kotlinc.bat",
        ],
        "swift": [
            *home.glob("AppData/Local/Programs/Swift/Toolchains/*/usr/bin/swift.exe"),
            Path("C:/Program Files/Swift/Toolchains/latest/usr/bin/swift.exe"),
        ],
        "swiftc": [
            *home.glob("AppData/Local/Programs/Swift/Toolchains/*/usr/bin/swiftc.exe"),
            Path("C:/Program Files/Swift/Toolchains/latest/usr/bin/swiftc.exe"),
        ],
        "ruby": [
            home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "ruby.exe",
            *Path("C:/").glob("Ruby*/bin/ruby.exe"),
            *Path("C:/Program Files").glob("Ruby*/bin/ruby.exe"),
            runtime_tools / "ruby" / "bin" / "ruby.exe",
        ],
        "php": [
            home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "php.exe",
            *home.glob("AppData/Local/Microsoft/WinGet/Packages/PHP.PHP.*_Microsoft.Winget.Source_*/php.exe"),
            *Path("C:/").glob("php*/php.exe"),
            *Path("C:/Program Files").glob("PHP*/php.exe"),
            runtime_tools / "php" / "php.exe",
        ],
        "lua": [
            home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "lua.exe",
            *home.glob("AppData/Local/Microsoft/WinGet/Packages/DEVCOM.Lua_Microsoft.Winget.Source_*/bin/lua.exe"),
            Path("C:/Program Files/Lua/lua.exe"),
            *Path("C:/Program Files").glob("Lua*/lua.exe"),
            runtime_tools / "lua" / "lua.exe",
        ],
        "sqlite3": [
            home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "sqlite3.exe",
            *home.glob("AppData/Local/Microsoft/WinGet/Packages/SQLite.SQLite_Microsoft.Winget.Source_*/sqlite3.exe"),
            Path("C:/Program Files/SQLite/sqlite3.exe"),
            runtime_tools / "sqlite" / "sqlite3.exe",
        ],
        "Rscript": [
            *Path("C:/Program Files/R").glob("R-*/bin/Rscript.exe"),
            Path("D:/b.WorkSpace/EngelToolchains/R/bin/Rscript.exe"),
            runtime_tools / "R" / "bin" / "Rscript.exe",
        ],
        "perl": [
            Path("C:/msys64/usr/bin/perl.exe"),
            Path("C:/Strawberry/perl/bin/perl.exe"),
            Path("C:/Program Files/Strawberry Perl/perl/bin/perl.exe"),
            runtime_tools / "strawberry-perl" / "perl" / "bin" / "perl.exe",
        ],
    }
    return glob_patterns.get(name, [])


def python_executable() -> str:
    bundled = ROOT / "runtime" / "python310" / "python.exe"
    if bundled.is_file():
        return str(bundled)
    return sys.executable or which_any("python", "py")


def dart_executable() -> str:
    direct_sdk = Path("D:/flutter_windows_3.41.9-stable/flutter/bin/cache/dart-sdk/bin/dart.exe")
    if direct_sdk.is_file():
        return str(direct_sdk)
    return which_any("dart")


def run_command(cmd: list[str], cwd: Path, timeout: int = 45) -> dict[str, Any]:
    started = time.perf_counter()
    shell = bool(cmd and cmd[0].lower().endswith((".bat", ".cmd")))
    env = dict(os.environ) if "os" in globals() else None
    if env is not None:
        home = Path.home()
        additions = [
            "C:\\msys64\\ucrt64\\bin",
            "C:\\msys64\\usr\\bin",
            str(Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links"),
            *[str(path.parent) for path in home.glob("AppData/Local/Programs/Swift/Toolchains/*/usr/bin/swift.exe")],
            *[str(path.parent) for path in home.glob("AppData/Local/Programs/Swift/Runtimes/*/usr/bin/swiftCore.dll")],
            *[str(path.parent) for path in home.glob("AppData/Local/Microsoft/WinGet/Packages/PHP.PHP.*_Microsoft.Winget.Source_*/php.exe")],
            *[str(path.parent) for path in home.glob("AppData/Local/Microsoft/WinGet/Packages/DEVCOM.Lua_Microsoft.Winget.Source_*/bin/lua.exe")],
            *[str(path.parent) for path in home.glob("AppData/Local/Microsoft/WinGet/Packages/SQLite.SQLite_Microsoft.Winget.Source_*/sqlite3.exe")],
        ]
        env["PATH"] = ";".join(additions + [env.get("PATH", "")])
        swift_sdks = sorted(home.glob("AppData/Local/Programs/Swift/Platforms/*/Windows.platform/Developer/SDKs/Windows.sdk"))
        if swift_sdks:
            env["SDKROOT"] = str(swift_sdks[-1])
    try:
        completed = subprocess.run(
            subprocess.list2cmdline(cmd) if shell else cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
            shell=shell,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {
            "command": cmd,
            "return_code": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_tail": tail(completed.stdout),
            "stderr_tail": tail(completed.stderr),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
    except FileNotFoundError as exc:
        return {
            "command": cmd,
            "return_code": None,
            "ok": False,
            "stdout_tail": "",
            "stderr_tail": str(exc),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": cmd,
            "return_code": None,
            "ok": False,
            "stdout_tail": tail(exc.stdout or ""),
            "stderr_tail": "timed out after %s seconds\n%s" % (timeout, tail(exc.stderr or "")),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }


def created_unverified(message: str) -> dict[str, Any]:
    return {
        "status": "created_unverified",
        "ok": True,
        "toolchain_available": False,
        "commands": [],
        "created_outputs": [],
        "message": message,
    }


def failed(message: str, commands: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "failed",
        "ok": False,
        "toolchain_available": True,
        "commands": commands,
        "created_outputs": [],
        "message": message,
    }


def passed(message: str, commands: list[dict[str, Any]], outputs: list[Path]) -> dict[str, Any]:
    return {
        "status": "passed",
        "ok": True,
        "toolchain_available": True,
        "commands": commands,
        "created_outputs": [str(path) for path in outputs],
        "message": message,
    }


def finalize_runtime(
    language_dir: Path,
    language: str,
    created_name: str,
    commands: list[dict[str, Any]],
    *,
    toolchain_available: bool = True,
) -> dict[str, Any]:
    created = language_dir / created_name
    if all(command.get("ok") for command in commands) and created.is_file():
        return passed(f"{language} executed and created {created_name}.", commands, [created])
    if toolchain_available:
        return failed(f"{language} toolchain ran but did not create {created_name}.", commands)
    return created_unverified(f"{language} source files were created; no local toolchain was found.")


def validate_python(language_dir: Path) -> dict[str, Any]:
    py = python_executable()
    if not py:
        return created_unverified("Python source created; no Python executable found.")
    command = run_command([py, "main.py"], language_dir)
    return finalize_runtime(language_dir, "Python", "python_created.json", [command])


def validate_javascript(language_dir: Path) -> dict[str, Any]:
    node = which_any("node")
    if not node:
        return created_unverified("JavaScript source created; Node.js was not found.")
    command = run_command([node, "main.js"], language_dir)
    return finalize_runtime(language_dir, "JavaScript", "javascript_created.json", [command])


def validate_typescript(language_dir: Path) -> dict[str, Any]:
    tsc = which_any("tsc")
    node = which_any("node")
    if not tsc:
        return created_unverified("TypeScript source created; tsc was not found.")
    commands = [run_command([tsc, "--target", "ES2020", "--module", "commonjs", "main.ts"], language_dir)]
    if commands[-1].get("ok") and node:
        commands.append(run_command([node, "main.js"], language_dir))
    created = language_dir / "typescript_created.json"
    if commands[-1].get("ok") and (created.is_file() or not node):
        outputs = [created] if created.is_file() else []
        return passed("TypeScript compiled%s." % (" and executed" if node else ""), commands, outputs)
    return failed("TypeScript validation failed.", commands)


def validate_html(language_dir: Path) -> dict[str, Any]:
    required = ["index.html", "style.css", "app.js"]
    missing = [name for name in required if not (language_dir / name).is_file()]
    if missing:
        return failed("HTML app is missing files: %s" % ", ".join(missing), [])
    html = (language_dir / "index.html").read_text(encoding="utf-8", errors="replace")
    js = (language_dir / "app.js").read_text(encoding="utf-8", errors="replace")
    if "Engel Multi-Language Creation" in html and "createdAt" in js:
        return passed("HTML/CSS/JS app files were created and internally verified.", [], [language_dir / "index.html"])
    return failed("HTML app markers were missing.", [])


def validate_powershell(language_dir: Path) -> dict[str, Any]:
    powershell = which_any("powershell", "pwsh")
    if not powershell:
        return created_unverified("PowerShell source created; PowerShell was not found.")
    command = run_command([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "main.ps1"], language_dir)
    return finalize_runtime(language_dir, "PowerShell", "powershell_created.json", [command])


def validate_bash(language_dir: Path) -> dict[str, Any]:
    bash = which_any("bash")
    if not bash:
        return created_unverified("Bash source created; bash was not found.")
    commands = [
        run_command([bash, "-n", "main.sh"], language_dir),
        run_command([bash, "main.sh"], language_dir),
    ]
    return finalize_runtime(language_dir, "Bash", "bash_created.json", commands)


def validate_batch(language_dir: Path) -> dict[str, Any]:
    command = run_command([str(language_dir / "main.bat")], language_dir)
    return finalize_runtime(language_dir, "Windows Batch", "batch_created.json", [command])


def validate_rust(language_dir: Path) -> dict[str, Any]:
    rustc = which_any("rustc")
    if not rustc:
        return created_unverified("Rust source created; rustc was not found.")
    exe = "main_rust.exe" if sys.platform.startswith("win") else "main_rust"
    commands = [
        run_command([rustc, "main.rs", "-o", exe], language_dir),
    ]
    if commands[-1].get("ok"):
        commands.append(run_command([str(language_dir / exe)], language_dir))
    return finalize_runtime(language_dir, "Rust", "rust_created.json", commands)


def validate_go(language_dir: Path) -> dict[str, Any]:
    go = which_any("go")
    if not go:
        return created_unverified("Go source created; go was not found.")
    command = run_command([go, "run", "main.go"], language_dir)
    return finalize_runtime(language_dir, "Go", "go_created.json", [command], toolchain_available=True)


def validate_c(language_dir: Path) -> dict[str, Any]:
    compiler = which_any("gcc", "clang")
    if not compiler:
        return created_unverified("C source created; gcc/clang was not found.")
    exe = "main_c.exe" if sys.platform.startswith("win") else "main_c"
    commands = [run_command([compiler, "main.c", "-o", exe], language_dir)]
    if commands[-1].get("ok"):
        commands.append(run_command([str(language_dir / exe)], language_dir))
    return finalize_runtime(language_dir, "C", "c_created.json", commands)


def validate_cpp(language_dir: Path) -> dict[str, Any]:
    compiler = which_any("g++", "clang++")
    if not compiler:
        return created_unverified("C++ source created; g++/clang++ was not found.")
    exe = "main_cpp.exe" if sys.platform.startswith("win") else "main_cpp"
    commands = [run_command([compiler, "main.cpp", "-o", exe], language_dir)]
    if commands[-1].get("ok"):
        commands.append(run_command([str(language_dir / exe)], language_dir))
    return finalize_runtime(language_dir, "C++", "cpp_created.json", commands)


def validate_csharp(language_dir: Path) -> dict[str, Any]:
    dotnet = which_any("dotnet")
    if not dotnet:
        return created_unverified("C# source created; dotnet was not found.")
    sdk_probe = run_command([dotnet, "--list-sdks"], language_dir)
    if not str(sdk_probe.get("stdout_tail") or "").strip():
        return created_unverified("C# source created; dotnet runtime exists but no .NET SDK was found.")
    command = run_command([dotnet, "run", "--project", "MultiLanguageCSharp.csproj", "--nologo"], language_dir, timeout=90)
    return finalize_runtime(language_dir, "C#", "csharp_created.json", [command])


def validate_java(language_dir: Path) -> dict[str, Any]:
    javac = which_any("javac")
    java = which_any("java")
    if not javac or not java:
        return created_unverified("Java source created; javac/java was not found.")
    commands = [
        run_command([javac, "Main.java"], language_dir),
    ]
    if commands[-1].get("ok"):
        commands.append(run_command([java, "Main"], language_dir))
    return finalize_runtime(language_dir, "Java", "java_created.json", commands)


def validate_kotlin(language_dir: Path) -> dict[str, Any]:
    kotlinc = which_any("kotlinc")
    java = which_any("java")
    if not kotlinc:
        return created_unverified("Kotlin source created; kotlinc was not found.")
    compiler_home = Path(kotlinc).resolve().parents[1]
    preloader = compiler_home / "lib" / "kotlin-preloader.jar"
    compiler = compiler_home / "lib" / "kotlin-compiler.jar"
    if java and preloader.is_file() and compiler.is_file():
        compile_cmd = [
            java,
            "-cp",
            str(preloader),
            "org.jetbrains.kotlin.preloading.Preloader",
            "-cp",
            str(compiler),
            "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler",
            "Main.kt",
            "-include-runtime",
            "-d",
            "main_kotlin.jar",
        ]
    else:
        compile_cmd = [kotlinc, "Main.kt", "-include-runtime", "-d", "main_kotlin.jar"]
    commands = [run_command(compile_cmd, language_dir, timeout=90)]
    if commands[-1].get("ok") and java:
        commands.append(run_command([java, "-jar", "main_kotlin.jar"], language_dir))
    return finalize_runtime(language_dir, "Kotlin", "kotlin_created.json", commands)


def validate_dart(language_dir: Path) -> dict[str, Any]:
    dart = dart_executable()
    if not dart:
        return created_unverified("Dart source created; dart was not found.")
    command = run_command([dart, "main.dart"], language_dir)
    return finalize_runtime(language_dir, "Dart", "dart_created.json", [command])


def validate_swift(language_dir: Path) -> dict[str, Any]:
    swiftc = which_any("swiftc")
    swift = which_any("swift")
    if not swiftc and not swift:
        return created_unverified("Swift source created; swift/swiftc was not found.")
    exe = "main_swift.exe" if sys.platform.startswith("win") else "main_swift"
    if swiftc:
        commands = [run_command([swiftc, "main.swift", "-o", exe], language_dir, timeout=90)]
        if commands[-1].get("ok"):
            commands.append(run_command([str(language_dir / exe)], language_dir, timeout=45))
        return finalize_runtime(language_dir, "Swift", "swift_created.json", commands)
    command = run_command([swift, "main.swift"], language_dir, timeout=90)
    return finalize_runtime(language_dir, "Swift", "swift_created.json", [command])


def validate_ruby(language_dir: Path) -> dict[str, Any]:
    ruby = which_any("ruby")
    if not ruby:
        return created_unverified("Ruby source created; ruby was not found.")
    command = run_command([ruby, "main.rb"], language_dir)
    return finalize_runtime(language_dir, "Ruby", "ruby_created.json", [command])


def validate_php(language_dir: Path) -> dict[str, Any]:
    php = which_any("php")
    if not php:
        return created_unverified("PHP source created; php was not found.")
    command = run_command([php, "main.php"], language_dir)
    return finalize_runtime(language_dir, "PHP", "php_created.json", [command])


def validate_lua(language_dir: Path) -> dict[str, Any]:
    lua = which_any("lua")
    if not lua:
        return created_unverified("Lua source created; lua was not found.")
    command = run_command([lua, "main.lua"], language_dir)
    return finalize_runtime(language_dir, "Lua", "lua_created.json", [command])


def validate_sql(language_dir: Path) -> dict[str, Any]:
    sqlite = which_any("sqlite3")
    if not sqlite:
        return created_unverified("SQL source created; sqlite3 was not found.")
    command = run_command([sqlite, "engel_language_creation.db", ".read main.sql"], language_dir)
    if command.get("ok") and (language_dir / "engel_language_creation.db").is_file():
        return passed("SQL executed through sqlite3 and created a database.", [command], [language_dir / "engel_language_creation.db"])
    return failed("SQL validation failed.", [command])


def validate_r(language_dir: Path) -> dict[str, Any]:
    rscript = which_any("Rscript")
    if not rscript:
        return created_unverified("R source created; Rscript was not found.")
    command = run_command([rscript, "main.R"], language_dir)
    return finalize_runtime(language_dir, "R", "r_created.json", [command])


def validate_perl(language_dir: Path) -> dict[str, Any]:
    perl = which_any("perl")
    if not perl:
        return created_unverified("Perl source created; perl was not found.")
    command = run_command([perl, "main.pl"], language_dir)
    return finalize_runtime(language_dir, "Perl", "perl_created.json", [command])


def language_specs() -> list[LanguageSpec]:
    return [
        LanguageSpec(
            "python",
            "Python",
            {
                "main.py": """\
import json
from pathlib import Path

payload = {"language": "Python", "created": True, "artifact": "python_created.json"}
Path("python_created.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print("Python created python_created.json")
""",
            },
            validate_python,
        ),
        LanguageSpec(
            "javascript",
            "JavaScript",
            {
                "main.js": """\
const fs = require("fs");
const payload = { language: "JavaScript", created: true, artifact: "javascript_created.json" };
fs.writeFileSync("javascript_created.json", JSON.stringify(payload, null, 2));
console.log("JavaScript created javascript_created.json");
""",
            },
            validate_javascript,
        ),
        LanguageSpec(
            "typescript",
            "TypeScript",
            {
                "main.ts": """\
declare function require(name: string): any;
const fs = require("fs");
const payload: { language: string; created: boolean; artifact: string } = {
  language: "TypeScript",
  created: true,
  artifact: "typescript_created.json",
};
fs.writeFileSync("typescript_created.json", JSON.stringify(payload, null, 2));
console.log("TypeScript created typescript_created.json");
""",
            },
            validate_typescript,
        ),
        LanguageSpec(
            "html_css_js",
            "HTML/CSS/Browser JavaScript",
            {
                "index.html": """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Engel Multi-Language Creation</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main class="panel">
    <h1>Engel Multi-Language Creation</h1>
    <p id="status">Waiting for browser JavaScript.</p>
  </main>
  <script src="app.js"></script>
</body>
</html>
""",
                "style.css": """\
body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #10151f;
  color: #eef5ff;
  font-family: Arial, sans-serif;
}
.panel {
  border: 1px solid #29d7ff;
  border-radius: 8px;
  padding: 24px;
  width: min(720px, 90vw);
  background: #151d2b;
}
""",
                "app.js": """\
const createdAt = new Date().toISOString();
document.getElementById("status").textContent =
  `Browser JavaScript created this state at ${createdAt}.`;
""",
            },
            validate_html,
        ),
        LanguageSpec(
            "powershell",
            "PowerShell",
            {
                "main.ps1": """\
$payload = [ordered]@{
    language = "PowerShell"
    created = $true
    artifact = "powershell_created.json"
}
$payload | ConvertTo-Json | Set-Content -Encoding UTF8 powershell_created.json
Write-Output "PowerShell created powershell_created.json"
""",
            },
            validate_powershell,
        ),
        LanguageSpec(
            "bash",
            "Bash",
            {
                "main.sh": """\
#!/usr/bin/env bash
set -euo pipefail
printf '{"language":"Bash","created":true,"artifact":"bash_created.json"}\\n' > bash_created.json
echo "Bash created bash_created.json"
""",
            },
            validate_bash,
        ),
        LanguageSpec(
            "windows_batch",
            "Windows Batch",
            {
                "main.bat": """\
@echo off
> batch_created.json echo {"language":"Windows Batch","created":true,"artifact":"batch_created.json"}
echo Windows Batch created batch_created.json
""",
            },
            validate_batch,
        ),
        LanguageSpec(
            "rust",
            "Rust",
            {
                "main.rs": """\
use std::fs;

fn main() {
    fs::write("rust_created.json", "{\\"language\\":\\"Rust\\",\\"created\\":true,\\"artifact\\":\\"rust_created.json\\"}\\n").unwrap();
    println!("Rust created rust_created.json");
}
""",
            },
            validate_rust,
        ),
        LanguageSpec(
            "go",
            "Go",
            {
                "main.go": """\
package main

import (
    "fmt"
    "os"
)

func main() {
    payload := []byte("{\\"language\\":\\"Go\\",\\"created\\":true,\\"artifact\\":\\"go_created.json\\"}\\n")
    if err := os.WriteFile("go_created.json", payload, 0644); err != nil {
        panic(err)
    }
    fmt.Println("Go created go_created.json")
}
""",
            },
            validate_go,
        ),
        LanguageSpec(
            "c",
            "C",
            {
                "main.c": """\
#include <stdio.h>

int main(void) {
    FILE *file = fopen("c_created.json", "w");
    if (!file) {
        return 1;
    }
    fputs("{\\"language\\":\\"C\\",\\"created\\":true,\\"artifact\\":\\"c_created.json\\"}\\n", file);
    fclose(file);
    puts("C created c_created.json");
    return 0;
}
""",
            },
            validate_c,
        ),
        LanguageSpec(
            "cpp",
            "C++",
            {
                "main.cpp": """\
#include <fstream>
#include <iostream>

int main() {
    std::ofstream file("cpp_created.json");
    file << "{\\"language\\":\\"C++\\",\\"created\\":true,\\"artifact\\":\\"cpp_created.json\\"}\\n";
    std::cout << "C++ created cpp_created.json\\n";
    return 0;
}
""",
            },
            validate_cpp,
        ),
        LanguageSpec(
            "csharp",
            "C#",
            {
                "MultiLanguageCSharp.csproj": """\
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
</Project>
""",
                "Program.cs": """\
using System;
using System.IO;

File.WriteAllText("csharp_created.json", "{\\"language\\":\\"C#\\",\\"created\\":true,\\"artifact\\":\\"csharp_created.json\\"}\\n");
Console.WriteLine("C# created csharp_created.json");
""",
            },
            validate_csharp,
        ),
        LanguageSpec(
            "java",
            "Java",
            {
                "Main.java": """\
import java.nio.file.Files;
import java.nio.file.Path;

public class Main {
    public static void main(String[] args) throws Exception {
        Files.writeString(Path.of("java_created.json"), "{\\"language\\":\\"Java\\",\\"created\\":true,\\"artifact\\":\\"java_created.json\\"}\\n");
        System.out.println("Java created java_created.json");
    }
}
""",
            },
            validate_java,
        ),
        LanguageSpec(
            "kotlin",
            "Kotlin",
            {
                "Main.kt": """\
import java.io.File

fun main() {
    File("kotlin_created.json").writeText("{\\"language\\":\\"Kotlin\\",\\"created\\":true,\\"artifact\\":\\"kotlin_created.json\\"}\\n")
    println("Kotlin created kotlin_created.json")
}
""",
            },
            validate_kotlin,
        ),
        LanguageSpec(
            "dart",
            "Dart",
            {
                "main.dart": """\
import 'dart:io';

void main() {
  File('dart_created.json').writeAsStringSync('{"language":"Dart","created":true,"artifact":"dart_created.json"}\\n');
  print('Dart created dart_created.json');
}
""",
            },
            validate_dart,
        ),
        LanguageSpec(
            "swift",
            "Swift",
            {
                "main.swift": """\
import Foundation

try "{\\"language\\":\\"Swift\\",\\"created\\":true,\\"artifact\\":\\"swift_created.json\\"}\\n".write(
    toFile: "swift_created.json",
    atomically: true,
    encoding: .utf8
)
print("Swift created swift_created.json")
""",
            },
            validate_swift,
        ),
        LanguageSpec(
            "ruby",
            "Ruby",
            {
                "main.rb": """\
File.write("ruby_created.json", "{\\"language\\":\\"Ruby\\",\\"created\\":true,\\"artifact\\":\\"ruby_created.json\\"}\\n")
puts "Ruby created ruby_created.json"
""",
            },
            validate_ruby,
        ),
        LanguageSpec(
            "php",
            "PHP",
            {
                "main.php": """\
<?php
file_put_contents("php_created.json", "{\\"language\\":\\"PHP\\",\\"created\\":true,\\"artifact\\":\\"php_created.json\\"}\\n");
echo "PHP created php_created.json\\n";
?>
""",
            },
            validate_php,
        ),
        LanguageSpec(
            "lua",
            "Lua",
            {
                "main.lua": """\
local file = io.open("lua_created.json", "w")
if not file then os.exit(1) end
file:write('{"language":"Lua","created":true,"artifact":"lua_created.json"}\\n')
file:close()
print("Lua created lua_created.json")
""",
            },
            validate_lua,
        ),
        LanguageSpec(
            "sql",
            "SQL",
            {
                "main.sql": """\
CREATE TABLE IF NOT EXISTS creation_receipt (
  language TEXT NOT NULL,
  created INTEGER NOT NULL,
  artifact TEXT NOT NULL
);
INSERT INTO creation_receipt(language, created, artifact)
VALUES ('SQL', 1, 'engel_language_creation.db');
""",
            },
            validate_sql,
        ),
        LanguageSpec(
            "r",
            "R",
            {
                "main.R": """\
writeLines('{"language":"R","created":true,"artifact":"r_created.json"}', "r_created.json")
cat("R created r_created.json\\n")
""",
            },
            validate_r,
        ),
        LanguageSpec(
            "perl",
            "Perl",
            {
                "main.pl": """\
use strict;
use warnings;
open(my $fh, ">", "perl_created.json") or die $!;
print $fh "{\\"language\\":\\"Perl\\",\\"created\\":true,\\"artifact\\":\\"perl_created.json\\"}\\n";
close($fh);
print "Perl created perl_created.json\\n";
""",
            },
            validate_perl,
        ),
    ]


def write_language_files(run_root: Path, spec: LanguageSpec) -> list[str]:
    language_dir = run_root / spec.key
    written: list[str] = []
    for relative, content in spec.files.items():
        path = language_dir / relative
        write_text(path, content)
        written.append(str(path))
    return written


def write_markdown_report(report_path: Path, result: dict[str, Any]) -> None:
    summary = result["summary"]
    lines = [
        "# Engel Known Code Language Creation Test",
        "",
        f"- Created at UTC: {result['created_at_utc']}",
        f"- Artifact root: `{result['artifact_root']}`",
        f"- Total languages: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Created but unverified: {summary['created_unverified']}",
        f"- Failed: {summary['failed']}",
        "",
        "| Language | Status | Created Files | Message |",
        "| --- | --- | ---: | --- |",
    ]
    for item in result["languages"]:
        lines.append(
            "| {language} | {status} | {count} | {message} |".format(
                language=item["language"],
                status=item["status"],
                count=len(item["source_files"]) + len(item.get("created_outputs", [])),
                message=str(item["message"]).replace("|", "\\|"),
            )
        )
    write_text(report_path, "\n".join(lines) + "\n")


def run_test() -> dict[str, Any]:
    created_at = iso_now()
    run_root = ARTIFACT_BASE / stamp()
    run_root.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    language_results: list[dict[str, Any]] = []
    for spec in language_specs():
        source_files = write_language_files(run_root, spec)
        language_dir = run_root / spec.key
        validation = spec.validate(language_dir)
        language_results.append(
            {
                "key": spec.key,
                "language": spec.display,
                "language_dir": str(language_dir),
                "source_files": source_files,
                **validation,
            }
        )

    summary = {
        "total": len(language_results),
        "passed": sum(1 for item in language_results if item["status"] == "passed"),
        "created_unverified": sum(1 for item in language_results if item["status"] == "created_unverified"),
        "failed": sum(1 for item in language_results if item["status"] == "failed"),
    }
    report_id = stamp()
    json_report = REPORT_DIR / f"ENGEL_KNOWN_CODE_LANGUAGE_CREATION_REPORT_{report_id}.json"
    markdown_report = REPORT_DIR / f"ENGEL_KNOWN_CODE_LANGUAGE_CREATION_REPORT_{report_id}.md"
    result = {
        "schema": "engel_known_code_language_creation_test_v1",
        "ok": summary["failed"] == 0,
        "created_at_utc": created_at,
        "updated_at_utc": iso_now(),
        "artifact_root": str(run_root),
        "report_json": str(json_report),
        "report_markdown": str(markdown_report),
        "summary": summary,
        "languages": language_results,
    }
    write_text(json_report, json.dumps(result, indent=2, sort_keys=True))
    write_markdown_report(markdown_report, result)
    return result


def main() -> int:
    result = run_test()
    print(json.dumps({
        "ok": result["ok"],
        "artifact_root": result["artifact_root"],
        "report_json": result["report_json"],
        "report_markdown": result["report_markdown"],
        "summary": result["summary"],
    }, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
