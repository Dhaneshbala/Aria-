"""
Coding Intelligence — Deep code analysis features.
Includes: Project Understanding, Architecture Viewer, Dependency Analysis,
Performance Optimiser, Security Scanner, Dead Code Finder, Auto Changelog.
"""
import json
import logging
import os
import re
from collections import defaultdict
from pathlib import Path

from services.ollama_service import OllamaService

logger = logging.getLogger(__name__)

ollama = OllamaService()

# File extensions to scan
CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css",
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt",
    ".java", ".cpp", ".c", ".h", ".go", ".rs", ".rb",
}

SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", "venv", ".venv",
    "dist", "build", ".next", ".nuxt", "vendor", "target",
}


class CodingIntelligence:

    # ── Project Understanding ─────────────────────────────────────────────────

    async def understand_project(self, project_path: str) -> dict:
        """Analyse a project and provide an overview."""
        path = Path(project_path)
        if not path.exists():
            return {"error": f"Path not found: {project_path}"}

        # Build file tree
        file_tree = self._build_file_tree(path)
        # Detect project type
        project_type = self._detect_project_type(path)
        # Count files by extension
        stats = self._count_files(path)
        # Get entry points
        entry_points = self._find_entry_points(path)

        return {
            "path": str(path),
            "type": project_type,
            "stats": stats,
            "file_tree": file_tree,
            "entry_points": entry_points,
            "total_files": sum(stats.values()),
        }

    async def explain_structure(self, project_path: str, model: str = "qwen3:8b") -> str:
        """Use AI to explain the project structure."""
        project = await self.understand_project(project_path)
        if "error" in project:
            return project["error"]

        system = (
            "You are a senior software engineer explaining a project's structure.\n"
            "Given the project overview below, explain:\n"
            "1. What the project does\n"
            "2. How it's organized\n"
            "3. Key files and their purposes\n"
            "4. Architecture patterns used\n"
            "5. Technology stack\n"
            "Be concise and use everyday examples."
        )
        prompt = (
            f"Project type: {project['type']}\n"
            f"Total files: {project['total_files']}\n"
            f"File tree:\n{json.dumps(project['file_tree'], indent=2)[:2000]}\n"
            f"Entry points: {', '.join(project['entry_points'])}\n"
            f"Stats: {json.dumps(project['stats'], indent=2)}"
        )
        try:
            result = await ollama.complete(model, prompt, system=system, max_tokens=1000)
            return result
        except Exception as e:
            return f"Error analysing project: {e}"

    # ── Architecture Viewer ───────────────────────────────────────────────────

    async def view_architecture(self, project_path: str) -> dict:
        """Generate a dependency graph of the project's internal structure."""
        path = Path(project_path)
        imports = defaultdict(list)

        for fpath in path.rglob("*"):
            if fpath.suffix in CODE_EXTENSIONS and fpath.is_file():
                if any(skip in fpath.parts for skip in SKIP_DIRS):
                    continue
                try:
                    content = fpath.read_text(errors="ignore")
                    rel = str(fpath.relative_to(path))
                    for line in content.split("\n")[:50]:
                        line = line.strip()
                        if line.startswith("import ") or line.startswith("from "):
                            imports[rel].append(line)
                except Exception:
                    continue

        # Build dependency graph
        nodes = list(imports.keys())
        edges = []
        for file, imps in imports.items():
            for imp in imps:
                # Try to resolve import to a file
                for node in nodes:
                    base = Path(node).stem
                    if base in imp:
                        edges.append({"source": file, "target": node, "import": imp})

        return {
            "nodes": nodes[:100],
            "edges": edges[:200],
            "total_files": len(nodes),
        }

    # ── Dependency Analysis ───────────────────────────────────────────────────

    async def analyse_dependencies(self, project_path: str) -> dict:
        """Analyse what packages are installed and why."""
        path = Path(project_path)
        deps = {}

        # Check package.json
        pkg_json = path / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                deps["npm"] = {
                    "dependencies": list(data.get("dependencies", {}).keys()),
                    "devDependencies": list(data.get("devDependencies", {}).keys()),
                }
            except Exception:
                pass

        # Check requirements.txt
        req_txt = path / "requirements.txt"
        if req_txt.exists():
            try:
                lines = req_txt.read_text().strip().split("\n")
                deps["pip"] = [l.strip().split("==")[0].split(">=")[0] for l in lines if l.strip() and not l.startswith("#")]
            except Exception:
                pass

        # Check pyproject.toml
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                # Simple extraction
                pkgs = re.findall(r'"([a-zA-Z0-9_-]+)"', content)
                deps["pyproject"] = list(set(pkgs))[:50]
            except Exception:
                pass

        return deps

    # ── Dead Code Finder ──────────────────────────────────────────────────────

    async def find_dead_code(self, project_path: str) -> dict:
        """Find unused imports, functions, and variables."""
        path = Path(project_path)
        issues = []

        for fpath in path.rglob("*"):
            if fpath.suffix not in {".py", ".js", ".jsx", ".ts", ".tsx"}:
                continue
            if any(skip in fpath.parts for skip in SKIP_DIRS):
                continue
            try:
                content = fpath.read_text(errors="ignore")
                rel = str(fpath.relative_to(path))
                lines = content.split("\n")

                # Find unused imports
                imports = []
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith("import ") or stripped.startswith("from "):
                        # Extract imported names
                        names = re.findall(r"import\s+(\w+)", stripped)
                        if not names:
                            names = re.findall(r"from\s+\w+\s+import\s+\{?(\w+)", stripped)
                        for name in names:
                            # Check if name is used elsewhere
                            used = any(
                                name in lines[j]
                                for j in range(len(lines))
                                if j != i
                            )
                            if not used:
                                issues.append({
                                    "file": rel,
                                    "line": i + 1,
                                    "type": "unused_import",
                                    "name": name,
                                    "code": stripped[:100],
                                })

                # Find potentially unused functions (simplified)
                if fpath.suffix == ".py":
                    func_defs = re.findall(r"def\s+(\w+)\s*\(", content)
                    for func in func_defs:
                        # Count occurrences (excluding def line)
                        occurrences = content.count(func) - 1
                        if occurrences <= 0:
                            issues.append({
                                "file": rel,
                                "type": "unused_function",
                                "name": func,
                            })

            except Exception:
                continue

        return {
            "total_issues": len(issues),
            "issues": issues[:100],
            "by_type": {
                t: len([i for i in issues if i["type"] == t])
                for t in set(i["type"] for i in issues)
            } if issues else {},
        }

    # ── Performance Optimiser ─────────────────────────────────────────────────

    async def analyse_performance(self, project_path: str, model: str = "qwen3:8b") -> str:
        """AI analysis of potential performance issues."""
        project = await self.understand_project(project_path)
        system = (
            "You are a performance engineering expert.\n"
            "Analyse the project and identify potential performance bottlenecks.\n"
            "Focus on: algorithm complexity, memory usage, I/O patterns, "
            "database queries, caching opportunities, and render performance.\n"
            "Provide specific, actionable suggestions."
        )
        prompt = (
            f"Project type: {project.get('type', 'unknown')}\n"
            f"Total files: {project.get('total_files', 0)}\n"
            f"Stats: {json.dumps(project.get('stats', {}), indent=2)}"
        )
        try:
            return await ollama.complete(model, prompt, system=system, max_tokens=800)
        except Exception as e:
            return f"Analysis failed: {e}"

    # ── Security Scanner ──────────────────────────────────────────────────────

    async def scan_security(self, project_path: str) -> dict:
        """Scan for common security issues."""
        path = Path(project_path)
        issues = []
        patterns = {
            "hardcoded_secret": [
                (r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']', "Potential hardcoded secret"),
                (r'["\']sk-[a-zA-Z0-9]{20,}["\']', "Potential API key"),
            ],
            "sql_injection": [
                (r'f["\'].*SELECT.*{.*}.*["\']', "F-string SQL query — potential injection"),
                (r'\.format\(.*SELECT', "Format string SQL query — potential injection"),
            ],
            "eval_usage": [
                (r'\beval\s*\(', "Use of eval() — potential code injection"),
                (r'\bexec\s*\(', "Use of exec() — potential code injection"),
            ],
            "insecure_random": [
                (r'import random\b', "Using 'random' module — use 'secrets' for security"),
            ],
            "debug_mode": [
                (r'DEBUG\s*=\s*True', "Debug mode enabled in production"),
                (r'app\.run\(.*debug\s*=\s*True', "Flask debug mode"),
            ],
        }

        for fpath in path.rglob("*"):
            if fpath.suffix not in CODE_EXTENSIONS:
                continue
            if any(skip in fpath.parts for skip in SKIP_DIRS):
                continue
            try:
                content = fpath.read_text(errors="ignore")
                rel = str(fpath.relative_to(path))
                for issue_type, pattern_list in patterns.items():
                    for pattern, desc in pattern_list:
                        for m in re.finditer(pattern, content, re.I):
                            issues.append({
                                "file": rel,
                                "type": issue_type,
                                "description": desc,
                                "match": m.group()[:80],
                            })
            except Exception:
                continue

        return {
            "total_issues": len(issues),
            "issues": issues[:50],
            "severity": "high" if any(i["type"] in {"hardcoded_secret", "sql_injection", "eval_usage"} for i in issues) else "low",
        }

    # ── Auto Changelog ────────────────────────────────────────────────────────

    async def generate_changelog(self, project_path: str, model: str = "qwen3:8b") -> str:
        """Generate changelog from git commits."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "-C", project_path, "log", "--oneline", "-30"],
                capture_output=True, text=True, timeout=10,
            )
            commits = result.stdout.strip()
            if not commits:
                return "No git history found."

            system = (
                "You are writing release notes.\n"
                "Convert these git commits into a clear, user-friendly changelog.\n"
                "Group by: Features, Fixes, Improvements.\n"
                "Be concise."
            )
            try:
                return await ollama.complete(model, commits, system=system, max_tokens=600)
            except Exception:
                return commits
        except Exception as e:
            return f"Git error: {e}"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_file_tree(self, path: Path, depth: int = 0, max_depth: int = 3) -> dict:
        tree = {}
        if depth >= max_depth:
            return tree
        try:
            for item in sorted(path.iterdir()):
                if item.name.startswith(".") or item.name in SKIP_DIRS:
                    continue
                if item.is_dir():
                    tree[f"{item.name}/"] = self._build_file_tree(item, depth + 1, max_depth)
                else:
                    tree[item.name] = item.stat().st_size
        except PermissionError:
            pass
        return tree

    def _detect_project_type(self, path: Path) -> str:
        if (path / "package.json").exists():
            return "Node.js"
        if (path / "requirements.txt").exists() or (path / "pyproject.toml").exists():
            return "Python"
        if (path / "Cargo.toml").exists():
            return "Rust"
        if (path / "go.mod").exists():
            return "Go"
        if (path / "pom.xml").exists():
            return "Java"
        if (path / "Gemfile").exists():
            return "Ruby"
        if any(path.glob("*.csproj")):
            return "C#"
        return "Unknown"

    def _count_files(self, path: Path) -> dict:
        counts = defaultdict(int)
        for f in path.rglob("*"):
            if f.is_file() and not any(skip in f.parts for skip in SKIP_DIRS):
                counts[f.suffix or "(no ext)"] += 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def _find_entry_points(self, path: Path) -> list[str]:
        points = []
        candidates = [
            "main.py", "app.py", "index.py", "server.py",
            "index.js", "index.jsx", "index.ts", "index.tsx",
            "main.js", "app.js", "server.js",
            "package.json", "pyproject.toml", "manage.py",
        ]
        for c in candidates:
            if (path / c).exists():
                points.append(c)
        return points
