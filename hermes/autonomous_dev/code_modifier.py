"""
Self-Modifying Code System
Safe autonomous code modification with validation and rollback
"""

import logging
import ast
import hashlib
import difflib
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('autonomous_dev.code_modifier')

class ModificationType(Enum):
    """Types of code modifications"""
    PARAMETER_TUNING = "parameter_tuning"
    ALGORITHM_REPLACEMENT = "algorithm_replacement"
    LOGIC_IMPROVEMENT = "logic_improvement"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    BUG_FIX = "bug_fix"
    FEATURE_ENHANCEMENT = "feature_enhancement"

class ModificationSafety(Enum):
    """Safety levels for modifications"""
    SAFE = "safe"
    MODERATE = "moderate"
    RISKY = "risky"
    EXPERIMENTAL = "experimental"

@dataclass
class CodeModification:
    """A proposed code modification"""
    modification_id: str
    file_path: str
    modification_type: ModificationType
    safety_level: ModificationSafety
    original_code: str
    modified_code: str
    changes: List[str]
    reason: str
    confidence: float
    expected_impact: str
    validation_tests: List[str]
    rollback_available: bool
    created_at: datetime

class CodeModifier:
    """Safe autonomous code modification system"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('code_modifier')

        # Configuration
        self.enabled = self.config.get('autonomous_dev.code_modifier.enabled', True)
        self.auto_apply_safe = self.config.get('autonomous_dev.code_modifier.auto_apply_safe', True)
        self.max_modifications_per_file = self.config.get('autonomous_dev.code_modifier.max_per_file', 5)

        # Safety settings
        self._safe_modifications = {
            ModificationType.PARAMETER_TUNING,
            ModificationType.PERFORMANCE_OPTIMIZATION
        }

        # Modification history
        self._modification_history = []
        self._rollback_stack = {}

    def analyze_and_suggest_modifications(self, file_path: str) -> List[CodeModification]:
        """
        Analyze code and suggest improvements

        Args:
            file_path: Path to code file

        Returns:
            List of suggested modifications
        """
        if not self.enabled:
            return []

        try:
            # Read file
            with open(file_path, 'r') as f:
                code = f.read()

            # Parse AST
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                self.logger.error(f"Syntax error in {file_path}: {e}")
                return []

            modifications = []

            # Analyze for improvement opportunities
            modifications.extend(self._analyze_performance_optimizations(file_path, code, tree))
            modifications.extend(self._analyze_parameter_tuning(file_path, code, tree))
            modifications.extend(self._analyze_code_quality(file_path, code, tree))
            modifications.extend(self._analyze_bug_patterns(file_path, code, tree))

            # Sort by confidence and safety
            modifications.sort(
                key=lambda m: (
                    {'safe': 4, 'moderate': 3, 'risky': 2, 'experimental': 1}[m.safety_level.value],
                    m.confidence
                ),
                reverse=True
            )

            self.logger.info(f"Found {len(modifications)} potential modifications for {file_path}")

            return modifications

        except Exception as e:
            self.logger.error(f"Error analyzing {file_path}: {e}")
            return []

    def _analyze_performance_optimizations(self, file_path: str, code: str, tree: ast.AST) -> List[CodeModification]:
        """Analyze for performance optimization opportunities"""
        modifications = []

        # Look for common performance patterns
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                modifications.extend(self._analyze_loop_optimizations(file_path, code, node))
            elif isinstance(node, ast.ListComp):
                modifications.extend(self._analyze_list_comprehensions(file_path, code, node))
            elif isinstance(node, ast.Call):
                modifications.extend(self._analyze_function_calls(file_path, code, node))

        return modifications

    def _analyze_loop_optimizations(self, file_path: str, code: str, loop_node: ast.For) -> List[CodeModification]:
        """Analyze for loop optimization opportunities"""
        modifications = []

        # Check for range(len(x)) pattern
        if (isinstance(loop_node.iter, ast.Call) and
            isinstance(loop_node.iter.func, ast.Name) and
            loop_node.iter.func.id == 'range' and
            len(loop_node.iter.args) == 1 and
            isinstance(loop_node.iter.args[0], ast.Call) and
            isinstance(loop_node.iter.args[0].func, ast.Name) and
            loop_node.iter.args[0].func.id == 'len'):

            # Suggest enumerate instead
            original_code = ast.get_source_segment(code, loop_node)
            if original_code:
                modified_code = original_code.replace(
                    'range(len(', 'for index, item in enumerate('
                ).replace(')', ')', 1)

                modifications.append(CodeModification(
                    modification_id=self._generate_modification_id(),
                    file_path=file_path,
                    modification_type=ModificationType.PERFORMANCE_OPTIMIZATION,
                    safety_level=ModificationSafety.SAFE,
                    original_code=original_code,
                    modified_code=modified_code,
                    changes=['Use enumerate() instead of range(len()) pattern'],
                    reason='enumerate() is more readable and slightly faster',
                    confidence=0.8,
                    expected_impact='Minor performance improvement, better readability',
                    validation_tests=['test_loop_equivalence'],
                    rollback_available=True,
                    created_at=datetime.now()
                ))

        return modifications

    def _analyze_list_comprehensions(self, file_path: str, code: str, list_comp: ast.ListComp) -> List[CodeModification]:
        """Analyze list comprehensions for optimization"""
        modifications = []

        # Check if list comprehension can be generator expression
        if hasattr(list_comp, 'parent'):
            # This would need more complex AST analysis
            pass

        return modifications

    def _analyze_function_calls(self, file_path: str, code: str, call_node: ast.Call) -> List[CodeModification]:
        """Analyze function calls for optimization"""
        modifications = []

        # Check for string concatenation in loops
        if isinstance(call_node.func, ast.Attribute) and call_node.func.attr == 'join':
            # Could suggest using f-strings in some cases
            pass

        return modifications

    def _analyze_parameter_tuning(self, file_path: str, code: str, tree: ast.AST) -> List[CodeModification]:
        """Analyze for parameter tuning opportunities"""
        modifications = []

        # Look for hardcoded numeric parameters
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                # Suggest making this a configurable parameter
                modifications.append(CodeModification(
                    modification_id=self._generate_modification_id(),
                    file_path=file_path,
                    modification_type=ModificationType.PARAMETER_TUNING,
                    safety_level=ModificationSafe.MODERATE,
                    original_code=f"{node.value}",
                    modified_code=f"CONFIG.get('{file_path}_param_{node.value}', {node.value})",
                    changes=['Make hardcoded value configurable'],
                    reason='Hardcoded values reduce flexibility',
                    confidence=0.6,
                    expected_impact='Improved configurability',
                    validation_tests=['test_parameter_default'],
                    rollback_available=True,
                    created_at=datetime.now()
                ))

        return modifications

    def _analyze_code_quality(self, file_path: str, code: str, tree: ast.AST) -> List[CodeModification]:
        """Analyze for code quality improvements"""
        modifications = []

        # Check for long functions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Count lines in function
                lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                if lines > 50:
                    modifications.append(CodeModification(
                        modification_id=self._generate_modification_id(),
                        file_path=file_path,
                        modification_type=ModificationType.LOGIC_IMPROVEMENT,
                        safety_level=ModificationSafe.MODERATE,
                        original_code=f"Function {node.name} ({lines} lines)",
                        modified_code=f"Consider breaking down {node.name} into smaller functions",
                        changes=[f'Break down {node.name} into smaller functions'],
                        reason=f'Function {node.name} is too long ({lines} lines)',
                        confidence=0.7,
                        expected_impact='Improved maintainability and testability',
                        validation_tests=['test_function_equivalence'],
                        rollback_available=True,
                        created_at=datetime.now()
                    ))

        return modifications

    def _analyze_bug_patterns(self, file_path: str, code: str, tree: ast.AST) -> List[CodeModification]:
        """Analyze for potential bug patterns"""
        modifications = []

        # Check for common anti-patterns
        for node in ast.walk(tree):
            # Check for mutable default arguments
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Call)):
                        modifications.append(CodeModification(
                            modification_id=self._generate_modification_id(),
                            file_path=file_path,
                            modification_type=ModificationType.BUG_FIX,
                            safety_level=ModificationSafe.SAFE,
                            original_code="Mutable default argument detected",
                            modified_code="Replace mutable default with None and check in function",
                            changes=['Fix mutable default argument bug'],
                            reason='Mutable default arguments can cause unexpected behavior',
                            confidence=0.9,
                            expected_impact='Prevent subtle bugs',
                            validation_tests=['test_default_argument_behavior'],
                            rollback_available=True,
                            created_at=datetime.now()
                        ))

        return modifications

    def apply_modification(self, modification: CodeModification) -> Dict[str, Any]:
        """
        Apply a code modification safely

        Args:
            modification: Modification to apply

        Returns:
            Result dictionary
        """
        try:
            # Safety checks
            if not self._is_safe_to_apply(modification):
                return {
                    'success': False,
                    'error': 'Modification not safe to apply automatically',
                    'safety_level': modification.safety_level.value
                }

            # Create backup
            backup_path = self._create_backup(modification.file_path)

            try:
                # Apply modification
                with open(modification.file_path, 'r') as f:
                    content = f.read()

                # Replace code (simple approach for now)
                if modification.original_code in content:
                    modified_content = content.replace(
                        modification.original_code,
                        modification.modified_code,
                        1  # Only replace first occurrence
                    )

                    # Write modified file
                    with open(modification.file_path, 'w') as f:
                        f.write(modified_content)

                    # Store for rollback
                    self._rollback_stack[modification.modification_id] = backup_path

                    # Add to history
                    self._modification_history.append(modification)

                    # Validate modification
                    validation_result = self._validate_modification(modification)

                    return {
                        'success': True,
                        'modification_id': modification.modification_id,
                        'backup_path': backup_path,
                        'validation': validation_result
                    }

                else:
                    return {
                        'success': False,
                        'error': 'Original code not found in file'
                    }

            except Exception as e:
                # Restore backup if modification failed
                self._restore_backup(modification.file_path, backup_path)
                return {
                    'success': False,
                    'error': f'Modification failed: {str(e)}',
                    'restored': True
                }

        except Exception as e:
            self.logger.error(f"Error applying modification {modification.modification_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _is_safe_to_apply(self, modification: CodeModification) -> bool:
        """Check if modification is safe to apply automatically"""
        # Safe modifications can be applied automatically
        if (modification.safety_level == ModificationSafety.SAFE and
            modification.confidence >= 0.8 and
            self.auto_apply_safe):
            return True

        # Moderate risk modifications require manual approval
        if modification.safety_level == ModificationSafety.MODERATE:
            return False

        # Risky and experimental modifications always require manual review
        return False

    def _create_backup(self, file_path: str) -> str:
        """Create backup of file before modification"""
        import shutil
        import os

        backup_path = f"{file_path}.backup_{int(datetime.now().timestamp())}"
        shutil.copy2(file_path, backup_path)
        return backup_path

    def _restore_backup(self, file_path: str, backup_path: str):
        """Restore file from backup"""
        import shutil
        shutil.copy2(backup_path, file_path)

    def _validate_modification(self, modification: CodeModification) -> Dict[str, Any]:
        """Validate applied modification"""
        validation_results = {
            'syntax_check': False,
            'import_check': False,
            'basic_tests': []
        }

        try:
            # Syntax check
            with open(modification.file_path, 'r') as f:
                content = f.read()
            ast.parse(content)
            validation_results['syntax_check'] = True
        except SyntaxError as e:
            validation_results['syntax_error'] = str(e)

        # Basic import check
        try:
            import subprocess
            result = subprocess.run(
                ['python', '-m', 'py_compile', modification.file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            validation_results['import_check'] = result.returncode == 0
            if result.returncode != 0:
                validation_results['import_error'] = result.stderr
        except Exception as e:
            validation_results['import_error'] = str(e)

        return validation_results

    def rollback_modification(self, modification_id: str) -> Dict[str, Any]:
        """
        Rollback a modification

        Args:
            modification_id: ID of modification to rollback

        Returns:
            Result dictionary
        """
        if modification_id not in self._rollback_stack:
            return {
                'success': False,
                'error': 'No rollback available for this modification'
            }

        try:
            backup_path = self._rollback_stack[modification_id]
            file_path = self._get_file_path_from_modification_id(modification_id)

            if file_path and os.path.exists(backup_path):
                self._restore_backup(file_path, backup_path)
                del self._rollback_stack[modification_id]

                return {
                    'success': True,
                    'message': f'Rolled back modification {modification_id}'
                }
            else:
                return {
                    'success': False,
                    'error': 'Backup file not found'
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'Rollback failed: {str(e)}'
            }

    def _get_file_path_from_modification_id(self, modification_id: str) -> Optional[str]:
        """Get file path from modification ID"""
        for mod in self._modification_history:
            if mod.modification_id == modification_id:
                return mod.file_path
        return None

    def get_modification_history(self, file_path: Optional[str] = None) -> List[CodeModification]:
        """Get modification history"""
        if file_path:
            return [m for m in self._modification_history if m.file_path == file_path]
        return self._modification_history.copy()

    def _generate_modification_id(self) -> str:
        """Generate unique modification ID"""
        return f"mod_{int(datetime.now().timestamp() * 1000)}_{hash(datetime.now()) % 10000}"

    def get_modification_stats(self) -> Dict[str, Any]:
        """Get modification statistics"""
        total_modifications = len(self._modification_history)
        applied_modifications = len([m for m in self._modification_history if m.rollback_available])

        by_type = {}
        by_safety = {}

        for mod in self._modification_history:
            mod_type = mod.modification_type.value
            safety = mod.safety_level.value

            by_type[mod_type] = by_type.get(mod_type, 0) + 1
            by_safety[safety] = by_safety.get(safety, 0) + 1

        return {
            'total_modifications': total_modifications,
            'applied_modifications': applied_modifications,
            'available_rollbacks': len(self._rollback_stack),
            'by_type': by_type,
            'by_safety': by_safety
        }