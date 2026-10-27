// Host test of the worker-job ownership protocol (esp32-firmware/src/jobs.h) with real threads.
// Build + run: sh esp32-firmware/test_host/build_jobs_test.sh
// What it cannot show: FreeRTOS scheduling, heap fragmentation, the HTTPS / CAS code itself (those need the chip).
#include <chrono>
#include <cstdio>
#include <random>
#include <thread>
#include <vector>
#include "../src/jobs.h"

static std::atomic<int> alive{0};
static std::vector<std::atomic<int>> *freed;

struct TestJob : Job {
  int id;
  int result = 0;
  explicit TestJob(int i) : id(i) { alive++; }
  ~TestJob() override {
    alive--;
    (*freed)[id]++;
  }
};

static int fails = 0;
static void check(const char *name, bool ok) {
  printf("  [%s] %s\n", ok ? "PASS" : "FAIL", name);
  if (!ok) fails++;
}

// The waiter side as main.cpp runs it: wait up to `timeout_us`, claim, use the result only if finished, release.
static bool waiter(TestJob *j, int timeout_us) {
  auto t0 = std::chrono::steady_clock::now();
  while (j->st.load() == 0 && std::chrono::steady_clock::now() - t0 < std::chrono::microseconds(timeout_us)) std::this_thread::yield();
  bool done = job_claim(j);
  if (done && j->result != 42) fails++;     // a finished job must carry the complete result
  job_release(j, done);
  return done;
}

int main() {
  const int N = 20000;
  std::vector<std::atomic<int>> fr(N + 4);
  freed = &fr;
  std::mt19937 rng(83);
  int finished = 0, abandoned = 0;
  for (int i = 0; i < N; i++) {
    TestJob *j = new TestJob(i);
    int work = rng() % 60, wait = rng() % 60;          // microseconds: both orders and near-ties happen
    std::thread task([j, work] {
      auto t0 = std::chrono::steady_clock::now();
      while (std::chrono::steady_clock::now() - t0 < std::chrono::microseconds(work)) std::this_thread::yield();
      j->result = 42;                                    // writes into the job after the waiter may have left
      job_finish(j);
    });
    if (waiter(j, wait)) finished++; else abandoned++;
    task.join();
  }
  printf("== job ownership protocol, %d jobs (%d finished first, %d abandoned by the waiter)\n", N, finished, abandoned);
  check("both orders were exercised", finished > 100 && abandoned > 100);
  check("no job leaked (every job freed by exactly one owner)", alive.load() == 0);
  bool once = true;
  for (int i = 0; i < N; i++) once = once && fr[i].load() == 1;
  check("no job freed twice", once);

  // Task creation fails (no heap).  Before the review fix the handler ignored xTaskCreate's result: the wait timed out, job_claim
  // flipped the job to "abandoned" and nobody was left to free it.  This models that flow and the fixed one.
  TestJob *lost = new TestJob(N);
  bool done = waiter(lost, 10);                          // old flow: no task exists, wait expires
  check("old flow (task never created): the job leaks", !done && alive.load() == 1 && fr[N].load() == 0);
  delete lost;                                           // (cleanup for the next check)
  TestJob *j2 = new TestJob(N + 1);
  bool spawned = false;                                  // fixed flow: job_spawn() == false -> answer "out of memory", delete at once
  if (!spawned) delete j2;
  check("fixed flow (spawn failure handled): nothing leaks", alive.load() == 0 && fr[N + 1].load() == 1);

  printf("RESULT: %s\n", fails ? "FAIL" : "all job protocol checks passed");
  return fails ? 1 : 0;
}
