from collections import defaultdict, deque

class DependencyGraph:
    def __init__(self) -> None:
        self._forward: dict[str,set[str]] = defaultdict(set)
        self._reverse: dict[str,set[str]] = defaultdict(set)

    def add_dependency(self, source: str, target: str) -> None:
        self._forward[source].add(target)
        self._reverse[target].add(source)
        if self._has_cycle():
            self._forward[source].remove(target)
            self._reverse[target].remove(source)
            raise ValueError("Dependency cycle")

    def affected_outputs(self, changed: set[str]) -> list[str]:
        q=deque(changed); seen=set(); result=[]
        while q:
            cur=q.popleft()
            for nxt in self._forward.get(cur,set()):
                if nxt not in seen:
                    seen.add(nxt); result.append(nxt); q.append(nxt)
        return result

    def _has_cycle(self) -> bool:
        nodes=set(self._forward)|set(self._reverse)
        indegree={n:len(self._reverse.get(n,set())) for n in nodes}
        q=deque(n for n,d in indegree.items() if d==0); seen=0
        while q:
            n=q.popleft(); seen+=1
            for c in self._forward.get(n,set()):
                indegree[c]-=1
                if indegree[c]==0: q.append(c)
        return seen!=len(nodes)
