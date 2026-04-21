# Evidence Dump — 2026-04-21 16:23 KST

폴백용 B-roll. **tomorrow(4/22)의 라이브 데모가 faucet/bridge 문제로 실패할 경우** 영상 인서트로 사용하거나, 제출 폼에 첨부.

모두 localhost 브리지(`http://localhost:3000`)에서 바로 긁어온 **원본 JSON** — 조작 없음. 캡처 시점: **2026-04-21 16:23 KST**, 페르소나 `demo (relaxed threshold)`, 510 raw + 12 premium signals 누적 상태.

## 파일 매핑

| 파일 | 출처 엔드포인트 | 영상 컷 매핑 |
|---|---|---|
| `health.json` | `GET /health` | 컷 3 오프닝 — 시스템 ok 카운터 |
| `persona.json` | `GET /policy/persona` | 컷 3 페르소나 스왑 시연 직전 상태 |
| `economics_summary.json` | `GET /economics/summary` | 컷 3 NetPnL 카드 B-roll |
| `tx_recent.json` | `GET /tx/recent` | 컷 4 Arc Explorer 연계 (paper 모드라 `[]`) |
| `signals_latest.json` | `GET /signals/latest` | 컷 3 raw signal stream B-roll |
| `signals_premium.json` | `GET /signals/premium` | 컷 3 premium 카드 — Gemini `justification` 포함 |
| `producer_reliability.json` | `GET /producer/reliability` | 컷 3 allocator heatmap 옆 |
| `allocation.json` | `GET /allocation` | 컷 3 AllocatorCard 현재 가중치 |
| `allocation_history.json` | `GET /allocation/history` | 컷 3 Q-table evolution 그래프 (30KB, 42 ticks) |
| `strategy_tick_pnl.json` | `GET /strategy/tick_pnl` | 컷 3 strategy-level PnL |
| `demo_run_*.log` | `python -m demo.run_demo` stdout | 컷 3 터미널 B-roll (카운터 증가) |

## 2.5분 smoke demo 델타 (실측)

| 지표 | before | after | Δ | 비고 |
|---|---|---|---|---|
| samples (executor outcome) | 11 | 22 | +11 | 150s 구간, ~14s/outcome |
| allocation_count | 42 | 50 | +8 | 20s 간격 알로케이터 틱 ✅ |
| raw signals | 500 | 500 | — | 500 cap (circular buffer) |
| premium signals | 12 | 13 | **+1** | ⚠️ 저빈도 — RECORDING_GUIDE 참조 |
| onchain_tx | 0 | 0 | — | paper 모드 (Circle 미주입) |

**Premium 저빈도는 데이터 임계 희소성 때문 — 버그 아님**. 대응은 `RECORDING_GUIDE_KR.md` 컷3 하단 참조.

## 사용 시나리오

### 시나리오 A — 내일 데모 성공 (기본 경로)
이 폴더는 **무시**. 라이브 tx stream을 녹화.

### 시나리오 B — faucet 막힘 (onchain tx=0)
- `tx_recent.json`은 `[]` 그대로 → 영상에서 "paper-mode validated end-to-end" 한 줄 추가
- `signals_premium.json`로 Gemini 어노테이션 품질 강조 (변동 가격이 signal quality에 반응한다는 증거)
- Arc Explorer 컷은 스킵하고 Circle Console `Wallets` 스크린샷으로 대체

### 시나리오 C — 브리지 다운
- 영상은 이 JSON들을 VS Code에 펼쳐놓고 코드/데이터 워크스루로 대체
- 경로: `docs/evidence/*.json` 풀스크린

## 검증 커맨드 (내일 시연 전 재확인)

```bash
cd /c/Users/user/hackerton/arc
diff <(curl -s http://localhost:3000/health) docs/evidence/health.json
# 오늘과 내일의 상태 차이 (signals 수·tx 수) 가 보여야 정상 운용
```
