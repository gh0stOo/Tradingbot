#!/usr/bin/env python3
"""
Comprehensive Python Code Quality Analysis Tool
Analyzes all Python files in the project without Unicode issues
"""

import os
import ast
import sys
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple

# Target directory
PROJECT_ROOT = Path(__file__).parent / "src"

class CodeAnalyzer:
    def __init__(self):
        self.issues = defaultdict(list)
        self.file_stats = {}
        self.total_lines = 0
        self.total_files = 0

    def analyze_file(self, filepath: Path) -> None:
        """Analyze a single Python file"""
        if not filepath.suffix == '.py':
            return

        self.total_files += 1
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
                self.total_lines += len(lines)

            # Parse AST
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                self.issues[str(filepath)].append(
                    ('CRITICAL', f'Syntax Error at line {e.lineno}: {e.msg}')
                )
                return

            # Get relative path for display
            rel_path = str(filepath.relative_to(PROJECT_ROOT))
            self.file_stats[rel_path] = {
                'lines': len(lines),
                'has_docstring': False,
                'has_type_hints': False,
                'issues_count': 0
            }

            # Check for common issues
            self._check_bare_excepts(content, rel_path)
            self._check_print_statements(content, rel_path)
            self._check_missing_docstrings(tree, rel_path)
            self._check_missing_type_hints(tree, rel_path)
            self._check_hardcoded_values(content, rel_path)
            self._check_todo_fixme(content, rel_path)
            self._check_imports(content, rel_path)

        except Exception as e:
            self.issues[str(filepath)].append(
                ('MEDIUM', f'Error analyzing file: {str(e)}')
            )

    def _check_bare_excepts(self, content: str, filepath: str) -> None:
        """Check for bare except clauses"""
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('except:') or stripped == 'except':
                self.issues[filepath].append(
                    ('CRITICAL', f'Line {i}: Bare except clause - use specific exceptions')
                )

    def _check_print_statements(self, content: str, filepath: str) -> None:
        """Check for print() statements instead of logging"""
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'print(' in line and not line.strip().startswith('#'):
                # Ignore print statements in comments or docstrings
                if 'logger' not in filepath and 'test' not in filepath.lower():
                    self.issues[filepath].append(
                        ('MEDIUM', f'Line {i}: Use logger instead of print(): {line.strip()[:60]}')
                    )

    def _check_missing_docstrings(self, tree: ast.AST, filepath: str) -> None:
        """Check for missing docstrings"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                has_docstring = (ast.get_docstring(node) is not None)
                if not has_docstring and not node.name.startswith('_'):
                    self.issues[filepath].append(
                        ('LOW', f'{node.__class__.__name__} "{node.name}" at line {node.lineno}: Missing docstring')
                    )

    def _check_missing_type_hints(self, tree: ast.AST, filepath: str) -> None:
        """Check for missing type hints"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip private/magic methods and methods in tests
                if node.name.startswith('_') or 'test' in filepath.lower():
                    continue

                # Check return type annotation
                if node.returns is None and node.name != '__init__':
                    self.issues[filepath].append(
                        ('LOW', f'Line {node.lineno}: Function "{node.name}" missing return type annotation')
                    )

                # Check argument type annotations
                for arg in node.args.args:
                    if arg.annotation is None and arg.arg not in ('self', 'cls'):
                        self.issues[filepath].append(
                            ('LOW', f'Line {node.lineno}: Arg "{arg.arg}" in "{node.name}" missing type hint')
                        )

    def _check_hardcoded_values(self, content: str, filepath: str) -> None:
        """Check for hardcoded credentials or sensitive values"""
        sensitive_patterns = [
            ('api_key', 'API key hardcoded'),
            ('api_secret', 'API secret hardcoded'),
            ('password', 'Password hardcoded'),
            ('webhook', 'Webhook URL hardcoded'),
            ('token', 'Token hardcoded'),
        ]

        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            lower_line = line.lower()
            for pattern, msg in sensitive_patterns:
                if pattern in lower_line and '=' in line and not line.strip().startswith('#'):
                    # Check if value is not from env or config
                    if 'os.getenv' not in line and 'config.get' not in line:
                        self.issues[filepath].append(
                            ('CRITICAL', f'Line {i}: {msg} - use environment variables')
                        )
                        break

    def _check_todo_fixme(self, content: str, filepath: str) -> None:
        """Check for TODO and FIXME comments"""
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'TODO' in line or 'FIXME' in line:
                self.issues[filepath].append(
                    ('MEDIUM', f'Line {i}: {line.strip()[:70]}')
                )

    def _check_imports(self, content: str, filepath: str) -> None:
        """Check for unused imports and import issues"""
        lines = content.split('\n')
        import_lines = []
        for i, line in enumerate(lines, 1):
            if line.startswith(('import ', 'from ')):
                import_lines.append((i, line))

        # Check for wildcard imports
        for i, line in import_lines:
            if 'import *' in line:
                self.issues[filepath].append(
                    ('MEDIUM', f'Line {i}: Wildcard import - use explicit imports')
                )

    def run(self) -> None:
        """Run analysis on all Python files"""
        python_files = list(PROJECT_ROOT.rglob('*.py'))

        for filepath in sorted(python_files):
            self.analyze_file(filepath)

        self.generate_report()

    def generate_report(self) -> None:
        """Generate and print analysis report"""
        print("=" * 80)
        print("CODE QUALITY ANALYSIS REPORT")
        print("=" * 80)
        print()

        # Summary statistics
        print("PROJECT STATISTICS:")
        print(f"  Total Python files: {self.total_files}")
        print(f"  Total lines of code: {self.total_lines}")
        print(f"  Average lines per file: {self.total_lines // max(1, self.total_files)}")
        print()

        # Issue summary
        critical_count = 0
        medium_count = 0
        low_count = 0

        for filepath, file_issues in self.issues.items():
            for severity, msg in file_issues:
                if severity == 'CRITICAL':
                    critical_count += 1
                elif severity == 'MEDIUM':
                    medium_count += 1
                elif severity == 'LOW':
                    low_count += 1

        print("ISSUE SUMMARY:")
        print(f"  CRITICAL issues: {critical_count}")
        print(f"  MEDIUM issues: {medium_count}")
        print(f"  LOW issues: {low_count}")
        print(f"  Total issues: {critical_count + medium_count + low_count}")
        print()

        # Detailed issues by file
        print("=" * 80)
        print("DETAILED ISSUES BY FILE:")
        print("=" * 80)
        print()

        for filepath in sorted(self.issues.keys()):
            file_issues = self.issues[filepath]

            # Group by severity
            critical = [i for i in file_issues if i[0] == 'CRITICAL']
            medium = [i for i in file_issues if i[0] == 'MEDIUM']
            low = [i for i in file_issues if i[0] == 'LOW']

            if file_issues:
                print(f"FILE: {filepath}")
                print(f"  Total issues: {len(file_issues)}")

                if critical:
                    print(f"  [CRITICAL] {len(critical)} issues:")
                    for _, msg in critical[:5]:  # Show top 5
                        print(f"    - {msg}")
                    if len(critical) > 5:
                        print(f"    ... and {len(critical) - 5} more")

                if medium:
                    print(f"  [MEDIUM] {len(medium)} issues:")
                    for _, msg in medium[:3]:  # Show top 3
                        print(f"    - {msg}")
                    if len(medium) > 3:
                        print(f"    ... and {len(medium) - 3} more")

                if low:
                    print(f"  [LOW] {len(low)} issues (type hints/docstrings)")

                print()

        # Top priority files
        print("=" * 80)
        print("TOP PRIORITY FILES (by issue count):")
        print("=" * 80)
        print()

        sorted_files = sorted(
            self.issues.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:10]

        for filepath, file_issues in sorted_files:
            print(f"{filepath}: {len(file_issues)} issues")

        print()
        print("Analysis complete. Check detailed output above.")

if __name__ == '__main__':
    analyzer = CodeAnalyzer()
    analyzer.run()
