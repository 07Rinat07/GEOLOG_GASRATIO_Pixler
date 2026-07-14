from collections import defaultdict, deque


class DependencyGraph:
    def __init__(self) -> None:
        self._forward: dict[str, set[str]] = defaultdict(set)
        self._reverse: dict[str, set[str]] = defaultdict(set)

    def add_dependency(self, source: str, target: str) -> None:
        self._forward[source].add(target)
        self._reverse[target].add(source)
        if self._has_cycle():
            self._forward[source].remove(target)
            self._reverse[target].remove(source)
            raise ValueError("Dependency cycle")

    def affected_outputs(self, changed: set[str]) -> list[str]:
        queue = deque(changed)
        seen: set[str] = set()
        result: list[str] = []
        while queue:
            current = queue.popleft()
            for dependent in self._forward.get(current, set()):
                if dependent not in seen:
                    seen.add(dependent)
                    result.append(dependent)
                    queue.append(dependent)
        return result

    def _has_cycle(self) -> bool:
        nodes = set(self._forward) | set(self._reverse)
        indegree = {node: len(self._reverse.get(node, set())) for node in nodes}
        queue = deque(node for node, degree in indegree.items() if degree == 0)
        seen = 0
        while queue:
            node = queue.popleft()
            seen += 1
            for dependent in self._forward.get(node, set()):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    queue.append(dependent)
        return seen != len(nodes)
