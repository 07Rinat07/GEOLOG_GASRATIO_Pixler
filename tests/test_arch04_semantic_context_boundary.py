from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path("src/geoworkbench")
SEMANTIC_MODULE = "geoworkbench.services.semantic_channels"
SHIM_PATH = ROOT / "services/semantic_channels.py"


def _attribute_path(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _attribute_path(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


def _imported_semantic_symbols(
    tree: ast.Module,
) -> tuple[set[str], set[str], set[str]]:
    dictionary_aliases: set[str] = set()
    factory_aliases: set[str] = set()
    module_aliases: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == SEMANTIC_MODULE:
            for alias in node.names:
                local = alias.asname or alias.name
                if alias.name == "SemanticChannelDictionary":
                    dictionary_aliases.add(local)
                elif alias.name == "default_semantic_channel_dictionary":
                    factory_aliases.add(local)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == SEMANTIC_MODULE:
                    module_aliases.add(alias.asname or alias.name)

    return dictionary_aliases, factory_aliases, module_aliases


def _annotation_mentions_dictionary(
    annotation: ast.AST | None,
    dictionary_aliases: set[str],
    module_aliases: set[str],
) -> bool:
    if annotation is None:
        return False
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name) and node.id in dictionary_aliases:
            return True
        if isinstance(node, ast.Attribute):
            owner = _attribute_path(node)
            if owner in {
                f"{module}.SemanticChannelDictionary" for module in module_aliases
            }:
                return True
    return False


def _is_semantic_factory_call(
    node: ast.AST,
    dictionary_aliases: set[str],
    factory_aliases: set[str],
    module_aliases: set[str],
) -> bool:
    if not isinstance(node, ast.Call):
        return False
    name = _attribute_path(node.func)
    if name in dictionary_aliases or name in factory_aliases:
        return True
    qualified = {
        *(f"{module}.SemanticChannelDictionary" for module in module_aliases),
        *(f"{module}.default_semantic_channel_dictionary" for module in module_aliases),
    }
    return name in qualified


def _target_paths(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, (ast.Name, ast.Attribute)):
        path = _attribute_path(node)
        return (path,) if path else ()
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(path for item in node.elts for path in _target_paths(item))
    return ()


def _expression_references_semantic_dictionary(
    node: ast.AST,
    tracked: set[str],
    dictionary_aliases: set[str],
    factory_aliases: set[str],
    module_aliases: set[str],
) -> bool:
    for child in ast.walk(node):
        if _is_semantic_factory_call(
            child,
            dictionary_aliases,
            factory_aliases,
            module_aliases,
        ):
            return True
        path = _attribute_path(child)
        if path in tracked:
            return True
    return False


def _semantic_dictionary_paths(
    tree: ast.Module,
    dictionary_aliases: set[str],
    factory_aliases: set[str],
    module_aliases: set[str],
) -> set[str]:
    tracked: set[str] = set()

    # Class-level annotations describe instance attributes for dataclasses and
    # ordinary classes, while call sites access them as self.<field>. Track both
    # forms so the audit cannot miss legacy resolver calls behind an annotated field.
    for class_node in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        for member in class_node.body:
            if not isinstance(member, ast.AnnAssign):
                continue
            if not _annotation_mentions_dictionary(
                member.annotation,
                dictionary_aliases,
                module_aliases,
            ):
                continue
            for path in _target_paths(member.target):
                tracked.add(path)
                if "." not in path:
                    tracked.add(f"self.{path}")

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = (
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            )
            if node.args.vararg is not None:
                args = (*args, node.args.vararg)
            if node.args.kwarg is not None:
                args = (*args, node.args.kwarg)
            for arg in args:
                if _annotation_mentions_dictionary(
                    arg.annotation,
                    dictionary_aliases,
                    module_aliases,
                ):
                    tracked.add(arg.arg)
        elif isinstance(node, ast.AnnAssign) and _annotation_mentions_dictionary(
            node.annotation,
            dictionary_aliases,
            module_aliases,
        ):
            tracked.update(_target_paths(node.target))

    assignments: list[tuple[tuple[str, ...], ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = tuple(path for target in node.targets for path in _target_paths(target))
            assignments.append((targets, node.value))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            assignments.append((_target_paths(node.target), node.value))
        elif isinstance(node, ast.NamedExpr):
            assignments.append((_target_paths(node.target), node.value))

    changed = True
    while changed:
        changed = False
        for targets, value in assignments:
            if not targets or not _expression_references_semantic_dictionary(
                value,
                tracked,
                dictionary_aliases,
                factory_aliases,
                module_aliases,
            ):
                continue
            before = len(tracked)
            tracked.update(targets)
            changed = changed or len(tracked) != before

    return tracked



def test_semantic_audit_tracks_annotated_instance_fields() -> None:
    tree = ast.parse(
        """
from geoworkbench.services.semantic_channels import SemanticChannelDictionary

class Consumer:
    semantic_dictionary: SemanticChannelDictionary

    def resolve_curve(self):
        return self.semantic_dictionary.resolve("ROP")
"""
    )
    dictionary_aliases, factory_aliases, module_aliases = _imported_semantic_symbols(tree)
    tracked = _semantic_dictionary_paths(
        tree,
        dictionary_aliases,
        factory_aliases,
        module_aliases,
    )

    assert "semantic_dictionary" in tracked
    assert "self.semantic_dictionary" in tracked
    legacy_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "resolve"
        and _attribute_path(node.func.value) in tracked
    ]
    assert len(legacy_calls) == 1


def test_production_semantic_consumers_do_not_call_legacy_resolve() -> None:
    violations: list[str] = []
    audited_consumers: set[Path] = set()

    for path in sorted(ROOT.rglob("*.py")):
        if path == SHIM_PATH:
            continue

        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        dictionary_aliases, factory_aliases, module_aliases = _imported_semantic_symbols(tree)
        if not (dictionary_aliases or factory_aliases or module_aliases):
            continue

        tracked = _semantic_dictionary_paths(
            tree,
            dictionary_aliases,
            factory_aliases,
            module_aliases,
        )
        if tracked:
            audited_consumers.add(path)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "resolve":
                continue

            owner = node.func.value
            owner_path = _attribute_path(owner)
            direct_factory = _is_semantic_factory_call(
                owner,
                dictionary_aliases,
                factory_aliases,
                module_aliases,
            )
            if owner_path in tracked or direct_factory:
                violations.append(
                    f"{path}:{node.lineno}: legacy SemanticChannelDictionary.resolve()"
                )

    assert audited_consumers, "No production SemanticChannelDictionary consumers were audited"
    assert violations == []


def test_legacy_resolve_is_only_a_context_delegation_shim() -> None:
    source = SHIM_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SHIM_PATH))
    dictionary_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SemanticChannelDictionary"
    )
    resolve = next(
        node
        for node in dictionary_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve"
    )

    context_assignment = next(
        (
            node
            for node in resolve.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "context"
            and isinstance(node.value, ast.Call)
            and _attribute_path(node.value.func) == "self.context"
        ),
        None,
    )
    assert context_assignment is not None

    delegated_return = next(
        (
            node
            for node in resolve.body
            if isinstance(node, ast.Return)
            and isinstance(node.value, ast.Call)
            and _attribute_path(node.value.func) == "self.resolve_context"
            and len(node.value.args) == 1
            and isinstance(node.value.args[0], ast.Name)
            and node.value.args[0].id == "context"
            and not node.value.keywords
        ),
        None,
    )
    assert delegated_return is not None

    forbidden_logic = [
        node
        for node in ast.walk(resolve)
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.Match))
    ]
    assert forbidden_logic == []
