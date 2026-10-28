# Live simulation WebSocket: `/ws/simulate`

All messages are JSON.

## Client to server

| Message | Effect |
| --- | --- |
| `{"type":"start","scenario":"peak_hour","mechanism":"kelly","speed":2}` | start (or restart) a run |
| `{"type":"pause"}` / `{"type":"resume"}` / `{"type":"step"}` | pause, resume, advance one tick while paused |
| `{"type":"set_speed","speed":4}` | ticks per second (0.2 to 20) |
| `{"type":"set_mechanism","mechanism":"max_min"}` | switch mechanism mid-run |
| `{"type":"set_capacity","capacity":30}` | change the link capacity in Mbps |
| `{"type":"add_user","user_type":"video","weight":2,"demand":8,"budget":10}` | add a user (only `user_type` is required) |
| `{"type":"remove_user","id":"video-3"}` | remove a user |
| `{"type":"update_user","id":"download-1","params":{"reported_demand":40}}` | change weight, budget, demand, or lie (`{"honest":true}` stops lying) |
| `{"type":"extend","ticks":60}` | keep going after the scenario ends |

## Server to client

| Message | Meaning |
| --- | --- |
| `{"type":"started","scenario":...,"ticks":60,"mechanism":...}` | run started |
| `{"type":"tick","record":{tick, mechanism, capacity, events, users[], metrics, extra},"total_ticks":60}` | one tick; `users[]` has each user's `rate`, `utility` and `starved` flag, and `extra` has the Kelly `price`, `bids` and `converged` |
| `{"type":"done","run_id":3}` | run finished and saved to the history |
| `{"type":"error","message":"..."}` | a command was rejected; the run continues |
