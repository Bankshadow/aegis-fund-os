# Loop backlog — tiny, verifiable tasks only

Format: `- [ ] <title> | check: <command>`

- [x] Confirm ship gate is green | check: powershell -File gate/verify.ps1
- [x] Run fast demo smoke | check: python run_demo.py --fast
- [x] E24 dual short_cfg experiment + log | check: python dual_short_cfg_demo.py
- [x] E25 conservative dual experiment + log | check: python dual_conservative_demo.py
