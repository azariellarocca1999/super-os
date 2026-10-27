// Worker-job ownership protocol shared by the firmware (main.cpp) and its host test (test_host/jobs_test.cpp).
#pragma once
#include <atomic>
#include <cstdint>

// Worker jobs (chat, CAS, Wikipedia/weather) run in their own task while the handler waits with a timeout.  The job lives on the heap and
// has two owners: when the handler gives up (timeout) the task is still running and will write into it later, so ownership is handed to the
// task (state 2) and the TASK frees it when it ends; when the task finishes first (state 1) the handler frees it.
struct Job {
  std::atomic<uint8_t> st{0};                    // 0 running, 1 finished, 2 abandoned by the waiter
  virtual ~Job() {}
};
static void job_finish(Job *j) {                 // called by the task as its last action before vTaskDelete
  uint8_t e = 0;
  if (!j->st.compare_exchange_strong(e, 1)) delete j;     // the waiter already left: nobody else will free it
}
static bool job_claim(Job *j) {                  // called by the waiter after its wait loop; true = the result is complete and usable
  uint8_t e = 0;
  return !j->st.compare_exchange_strong(e, 2);   // false = abandoned (the task frees the job)
}
static void job_release(Job *j, bool finished) { if (finished) delete j; }
