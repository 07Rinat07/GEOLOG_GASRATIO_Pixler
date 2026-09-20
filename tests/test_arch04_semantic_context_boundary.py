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


def _parent_map(tree: ast.Module) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


_SCOPE_TYPES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _containing_scope(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
    tree: ast.Module,
) -> ast.AST:
    current = parents.get(node)
    while current is not None and not isinstance(current, _SCOPE_TYPES):
        current = parents.get(current)
    return current or tree


def _scope_chain(
    scope: ast.AST,
    parents: dict[ast.AST, ast.AST],
    tree: ast.Module,
):
    current = scope
    while True:
        yield current
        if current is tree:
            return
        current = _containing_scope(current, parents, tree)


def _path_is_tracked(
    path: str,
    scope: ast.AST,
    tracked: dict[ast.AST, set[str]],
    parents: dict[ast.AST, ast.AST],
    tree: ast.Module,
) -> bool:
    return any(path in tracked.get(candidate, set()) for candidate in _scope_chain(scope, parents, tree))


def _expression_references_semantic_dictionary(
    node: ast.AST,
    scope: ast.AST,
    tracked: dict[ast.AST, set[str]],
    parents: dict[ast.AST, ast.AST],
    tree: ast.Module,
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
        if path is not None and _path_is_tracked(
            path,
            scope,
            tracked,
            parents,
            tree,
        ):
            return True
    return False


def _semantic_dictionary_paths(
    tree: ast.Module,
    dictionary_aliases: set[str],
    factory_aliases: set[str],
    module_aliases: set[str],
) -> tuple[dict[ast.AST, set[str]], dict[ast.AST, ast.AST]]:
    parents = _parent_map(tree)
    tracked: dict[ast.AST, set[str]] = {
        node: set()
        for node in ast.walk(tree)
        if isinstance(node, _SCOPE_TYPES)
    }
    tracked.setdefault(tree, set())

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
                    tracked[node].add(arg.arg)
        elif isinstance(node, ast.AnnAssign) and _annotation_mentions_dictionary(
            node.annotation,
            dictionary_aliases,
            module_aliases,
        ):
            scope = _containing_scope(node, parents, tree)
            targets = _target_paths(node.target)
            tracked.setdefault(scope, set()).update(targets)
            if (
                isinstance(scope, ast.ClassDef)
                and parents.get(node) is scope
            ):
                tracked[scope].update(
                    f"self.{path}" for path in targets if "." not in path
                )

    assignments: list[tuple[ast.AST, tuple[str, ...], ast.AST]] = []
    for node in ast.walk(tree):
        scope = _containing_scope(node, parents, tree)
        if isinstance(node, ast.Assign):
            targets = tuple(
                path
                for target in node.targets
                for path in _target_paths(target)
            )
            assignments.append((scope, targets, node.value))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            assignments.append((scope, _target_paths(node.target), node.value))
        elif isinstance(node, ast.NamedExpr):
            assignments.append((scope, _target_paths(node.target), node.value))

    changed = True
    while changed:
        changed = False
        for scope, targets, value in assignments:
            if not targets or not _expression_references_semantic_dictionary(
                value,
                scope,
                tracked,
                parents,
                tree,
                dictionary_aliases,
                factory_aliases,
                module_aliases,
            ):
                continue
            before = len(tracked.setdefault(scope, set()))
            tracked[scope].update(targets)
            changed = changed or len(tracked[scope]) != before

    return tracked, parents


def _legacy_semantic_resolve_lines(tree: ast.Module) -> list[int]:
    dictionary_aliases, factory_aliases, module_aliases = _imported_semantic_symbols(tree)
    if not (dictionary_aliases or factory_aliases or module_aliases):
        return []

    tracked, parents = _semantic_dictionary_paths(
        tree,
        dictionary_aliases,
        factory_aliases,
        module_aliases,
    )
    violations: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "resolve":
            continue
        owner = node.func.value
        owner_path = _attribute_path(owner)
        scope = _containing_scope(node, parents, tree)
        direct_factory = _is_semantic_factory_call(
            owner,
            dictionary_aliases,
            factory_aliases,
            module_aliases,
        )
        if direct_factory or (
            owner_path is not None
            and _path_is_tracked(owner_path, scope, tracked, parents, tree)
        ):
            violations.append(node.lineno)
    return violations


def test_semantic_audit_scopes_instance_fields_to_declaring_class() -> None:
    tree = ast.parse(
        """
from geoworkbench.services.semantic_channels import SemanticChannelDictionary

class SemanticConsumer:
    resolver: SemanticChannelDictionary

    def resolve_curve(self):
        return self.resolver.resolve("ROP")

class OtherResolver:
    def resolve(self, value):
        return value

class UnrelatedConsumer:
    resolver: OtherResolver

    def resolve_curve(self):
        return self.resolver.resolve("ROP")
"""
    )

    assert len(_legacy_semantic_resolve_lines(tree)) == 1


def test_semantic_audit_tracks_nested_annotated_instance_fields() -> None:
    tree = ast.parse(
        """
from geoworkbench.services.semantic_channels import SemanticChannelDictionary

def build_consumer():
    class NestedConsumer:
        semantic_dictionary: SemanticChannelDictionary

        def resolve_curve(self):
            return self.semantic_dictionary.resolve("ROP")

    return NestedConsumer()
"""
    )

    assert len(_legacy_semantic_resolve_lines(tree)) == 1


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

        tracked, _parents = _semantic_dictionary_paths(
            tree,
            dictionary_aliases,
            factory_aliases,
            module_aliases,
        )
        if any(tracked.values()):
            audited_consumers.add(path)

        violations.extend(
            f"{path}:{line}: legacy SemanticChannelDictionary.resolve()"
            for line in _legacy_semantic_resolve_lines(tree)
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
