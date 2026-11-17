# Phase 1 test evidence

Raw evidence behind [`docs/PHASE1_COMPLETION_REPORT.md`](../../PHASE1_COMPLETION_REPORT.md).
Every file here was copied unchanged from the test sessions of 16–17 Nov 2026,
except `repeatability/summary.csv`, which is derived from `results.jsonl`.
Log files were renamed from `.log` to `.txt` because the repository
`.gitignore` excludes `*.log`; their content is unchanged.

## `repeatability/`: final five-run validation (17 Nov 2026)

These are the acceptance-test results. Each run restarted the complete stack
(`run_system.sh` with `FYP_DEPTH_SOURCE=gazebo`), sent the goal (2.0, 0.0)
with `send_test_goal.sh`, and judged success by Gazebo's ground-truth pose.

| File | Content |
|---|---|
| `results.jsonl` | One JSON record per run, with fields listed below. **Primary result file.** |
| `summary.csv` | The same five runs as a table (derived from `results.jsonl`). |
| `trials_console.txt` | Console output of the harness for all five runs. |
| `runN/amcl_trace.txt` | Every `/amcl_pose` update next to the true pose (`/odom`) at the same stamp: error, AMCL 1-σ, pitch, velocity. |
| `runN/goal_action_output.txt` | Output of `send_test_goal.sh`, including the Nav2 action result. |
| `runN/nav2_log_during_goal.txt` | Nav2 log lines written while the goal ran. Used to count recovery behaviours. |
| `runN/nav2_log_bringup.txt` | Full Nav2 log from start-up to the end of the run. |
| `runN/run_system_output.txt` | Output of `run_system.sh` (start-up phases). |

Fields in `results.jsonl`:
- Pre-checks: `lifecycle` states, `params` (AMCL and goal checker, read from the running nodes), `rates`, `tf_ok`.
- Start state: `init_truth`, `init_amcl`.
- Outcome: `result` (Nav2), `duration_s`, `stop`.
- Final state: `final_truth`, `final_amcl`, `amcl_sigma`.
- Accuracy: `gt_dist_from_goal`, `loc_error`.
- Other: `events` (Nav2 log events), `amcl_updates`, `pass`.

Known benign messages in these logs:
- `goal_action_output.txt` of run 1 contains a `BrokenPipeError`. It comes from
  `send_test_goal.sh` piping `ros2 service list` into `grep -q`, which closes the
  pipe early. The goal was then sent normally and finished `SUCCEEDED`.
- The AMCL trace logger was stopped by SIGINT during cleanup. Its shutdown
  traceback (`trace.err`) was not copied.

## `development/`: tuning history (16–17 Nov 2026)

These runs were made while the configuration was still being changed. They
are kept to document why the final parameters were chosen. **They are not
acceptance results.**

| File | Configuration | Ground-truth result |
|---|---|---|
| `baseline_before_amcl_tuning_pose_log.txt` | Gazebo depth scan, default AMCL, default goal checker (0.25 m) | final (1.840, −0.297), 0.339 m ❌ |
| `tuning_run1_tol0.10_pose_log.txt` | Tuned AMCL, goal tolerance 0.10 m | final (1.887, −0.135), 0.176 m ❌ |
| `tuning_run2_tol0.10_amcl_trace.txt` | Same, after a robot pose reset | final (1.887, −0.133), 0.174 m ❌ |
| `tuning_run3_tol0.05_amcl_trace.txt`, `_final.txt` | Goal tolerance 0.05 m, set live on the running controller | 0.078 m ✅, but needed 5 progress failures and 1 spin recovery (153.8 s) |
| `tuning_run4_tol0.05_amcl_trace.txt`, `_final.txt` | Final configuration, fresh start from the launch files | 0.130 m ✅, no recoveries |
| `tuning_runs1to3_nav2_log.txt` | Nav2 log covering tuning runs 1–3 | Shows the run-3 recoveries |
| `scan_vs_world_while_moving.txt` | Live `/scan` compared with a ray-cast of `indoor_world.sdf` while driving | median \|error\| 1.2 cm, 99.7 % of beams within 10 cm |
| `phone_mode_regression_startup.txt` | `run_system.sh` in default phone mode | Start-up only; see the report for the parameter checks |

In the trace and pose-log files, "true" is `/odom`. Gazebo's odometry plugin
reports the simulator's true pose; this was cross-checked against
`/world/indoor_world/pose/info` several times during development.

## `scripts/`: test harness used to produce this evidence

Copied verbatim. They are **test tools, not part of the robot software**.

| Script | Purpose |
|---|---|
| `run_trial.sh` | One independent trial: clean stop, fresh `run_system.sh`, pre-checks, goal, ground truth, JSON record, cleanup. |
| `trial_probe.py` | Topic rates, and "robot stopped" detection (\|v\|,\|ω\| < 0.01 for 3 s of simulation time). |
| `tf_check.py` | Looks up the TF chain with a simulation-time listener. |
| `amcl_cov.py` | Reads the latched `/amcl_pose` and its 1-σ values. |
| `phase1_amcl_trace.py` | Per-update AMCL vs true-pose logger. |
| `phase1_pose_log.py` | Once-per-second pose logger (development runs). |
| `scan_vs_world.py` | Compares `/scan` with a 2-D ray-cast of the world SDF. |
| `reset_robot.sh` | Resets the robot in Gazebo and re-initialises AMCL (development runs 2–3 only). |
| `stop_stack.sh` | Stops the processes this test starts, by PID. |

The scripts contain the absolute scratch path used during testing
(`S=/tmp/claude-1000/...`). Edit `S` (and `R` in `run_trial.sh`) before
reusing them; see "Reproducing the tests" in the report.
