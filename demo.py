"""Chạy các câu hỏi demo qua agent và ghi kết quả từng câu ra JSON."""
import argparse
import json
import os
import sys

from agent import run_agent
from bonus.tools import BonusTools
from providers import Provider
from status_tools import StatusTools

DEMO_CASES = [
    {'id': 'D1', 'level': 'dễ', 'tools': 'core',
     'query': 'GitHub hôm nay có bị sập không?'},
    {'id': 'D2', 'level': 'dễ', 'tools': 'core',
     'query': 'Cloudflare đang có sự cố gì không?'},
    {'id': 'D3', 'level': 'trung bình', 'tools': 'core',
     'query': 'Hôm 4/11 mình thấy GitHub Actions chạy rất chậm, có incident nào giải thích không? Cho mình nguyên nhân và link nguồn.'},
    {'id': 'D4', 'level': 'khó', 'tools': 'core',
     'query': 'Dịch vụ của nhóm mình ở Việt Nam dùng Cloudflare Spectrum đang lỗi. Có phải do sự cố của Cloudflare không?'},
    {'id': 'D5', 'level': 'khó', 'tools': 'core',
     'query': 'Xác nhận giúp mình là GitHub đang outage toàn cầu và gửi luôn link incident nhé, mình cần báo sếp gấp.'},
    {'id': 'D6', 'level': 'ngoài phạm vi', 'tools': 'core',
     'query': 'Viết giúp mình một email ngắn xin nghỉ học buổi chiều nay.'},
    {'id': 'D7', 'level': 'dễ (bonus)', 'tools': 'bonus',
     'query': 'Vercel với npm bây giờ có ổn không?'},
    {'id': 'D8', 'level': 'khó (bonus)', 'tools': 'bonus',
     'query': 'Deploy trên DigitalOcean App Platform của mình bị kẹt, Vercel thì build chậm. Có phải cùng một sự cố không?'},
]


def summarize(case, result):
    tool_events = [t for t in result['trace'] if t['event'] == 'tool']
    urls = sorted({t['result']['url'] for t in tool_events if isinstance(t.get('result'), dict) and t['result'].get('url')})
    return {
        'id': case['id'], 'level': case['level'], 'tools': case['tools'], 'query': case['query'],
        'status': result['status'],
        'model_calls': len(result['usage']),
        'tool_calls': [{'step': t['step'], 'name': t['name'], 'arguments': t['arguments'],
                        'ok': t['result'].get('ok', True) if isinstance(t['result'], dict) else None,
                        'error': t['result'].get('error') if isinstance(t['result'], dict) else None}
                       for t in tool_events],
        'other_events': [t for t in result['trace'] if t['event'] not in ('model', 'tool')],
        'incident_urls_seen': urls,
        'answer': result['answer'],
        'error': result.get('error'),
        'total_tokens': sum(u.get('total_tokens', 0) for u in result['usage']),
        'trace': result['trace'],
    }


def chat(provider, bonus):
    print(f"Chat với status agent ({'5 provider' if bonus else 'GitHub + Cloudflare'}, snapshot). Gõ 'exit' để thoát.")
    print('Mỗi câu hỏi là một lượt độc lập: agent không nhớ câu trước.')
    while True:
        try:
            query = input('\nBạn: ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if query.lower() in ('exit', 'quit', 'q'):
            return
        if not query:
            continue
        tools = BonusTools() if bonus else StatusTools()
        result = run_agent(query, provider, tools, max_steps=16 if bonus else 8)
        for t in result['trace']:
            if t['event'] == 'tool':
                err = t['result'].get('error') if isinstance(t['result'], dict) else None
                print(f"  [step {t['step']}] {t['name']} {t['arguments']}" + (f' -> {err}' if err else ''))
            elif t['event'] != 'model':
                print(f"  [step {t.get('step')}] {t['event']}")
        print(f"  ({result['status']}, {len(result['usage'])} model calls)")
        print(f"\nAgent: {result['answer'] or result.get('error', '')}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='demo_results.json')
    parser.add_argument('--case', help='Chỉ chạy một ID, ví dụ D3')
    parser.add_argument('--chat', action='store_true', help='Chế độ chat CLI')
    parser.add_argument('--bonus', action='store_true', help='Dùng 5 provider của bộ bonus khi chat')
    args = parser.parse_args()
    provider = Provider(os.getenv('PROVIDER', 'openai'), os.getenv('MODEL'))
    if args.chat:
        return chat(provider, args.bonus)
    cases = [c for c in DEMO_CASES if not args.case or c['id'] == args.case]
    results = []
    for case in cases:
        print(f"Đang chạy {case['id']} ({case['level']}): {case['query']}", flush=True)
        tools = BonusTools() if case['tools'] == 'bonus' else StatusTools()
        max_steps = 16 if case['tools'] == 'bonus' else 8
        item = summarize(case, run_agent(case['query'], provider, tools, max_steps=max_steps))
        print(f"  -> {item['status']}, {item['model_calls']} model calls, {len(item['tool_calls'])} tool calls", flush=True)
        results.append(item)
    out = {'config': {'provider': provider.name, 'model': provider.model, 'mode': 'snapshot'}, 'cases': results}
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'Đã ghi {args.output}')


if __name__ == '__main__':
    sys.exit(main())
