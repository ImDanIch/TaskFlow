"""Run frozen queries over real MCP stdio, saving paths and source context."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from guardrails.policy import PolicyEvaluator

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/rag'


async def run(mode):
    vault = ROOT.parent / 'TaskFlow-KB'
    policy = PolicyEvaluator(vault)
    cases = json.loads((OUT / 'queries.json').read_text(encoding='utf-8'))
    args = ['-m', 'mcp_server.server']
    if mode == 'before':
        # Reuse the preserved original substring algorithm, through the same MCP.
        args = ['-c', 'from mcp_server.vault import Vault; Vault.search_notes = Vault.lexical_search_notes; from mcp_server.server import main; main()']
    params = StdioServerParameters(command=sys.executable,
        args=args, cwd=str(ROOT),
        env={**os.environ, 'TASKFLOW_KB_PATH': str(vault),
             'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'})
    results = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=60)
            listed = await session.list_tools()
            schema = next(t.inputSchema for t in listed.tools if t.name == 'search_notes')
            assert set(schema['properties']) == {'query'}
            for case in cases:
                start = time.perf_counter()
                response = await asyncio.wait_for(session.call_tool(
                    'search_notes', {'query': case['query']}), timeout=45)
                assert not response.isError, response
                elapsed = time.perf_counter() - start
                paths = response.structuredContent['result']
                sources = {}
                for path in paths[:5]:
                    assert policy.evaluate('read', path).decision == 'allow'
                    note = await session.call_tool('get_note', {'note_path': path})
                    assert not note.isError
                    sources[path] = note.content[0].text
                rank = paths[:5].index(case['gold']) + 1 if case['gold'] in paths[:5] else None
                results.append({**case, 'paths': paths, 'rank': rank, 'seconds': elapsed,
                                'sources': sources})
                print(f'query {len(results)}: rank={rank}, {elapsed:.2f}s', flush=True)
    payload = {'mode': mode, 'transport': 'fresh MCP SDK stdio', 'schema': schema,
               'results': results, 'hit_at_5': sum(r['rank'] is not None for r in results)/10,
               'mrr_at_5': sum(1/r['rank'] if r['rank'] else 0 for r in results)/10}
    (OUT / f'{mode}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in payload.items() if k != 'results'},ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(run(sys.argv[1]))
