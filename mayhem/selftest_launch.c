/* Thin ELF launcher for the functional self-test.
 *
 * mayhem/test.sh runs THIS binary (a project, non-system ELF) rather than calling python3
 * directly, so the anti-reward-hack sabotage check (verify-repo §6.3) can neuter it: the
 * sabotage LD_PRELOADs an _exit(0) constructor into every non-system executable. When neutered
 * this launcher exits before exec'ing python, the self-test prints nothing, and test.sh reports
 * a failure — proving the oracle asserts BEHAVIOR, not just exit status. (python3 lives under
 * /usr/bin and is deliberately spared by the sabotage, so a test that shelled out to it directly
 * could never be neutered.) Under normal runs it just execs python3 on selftest.py. */
#include <unistd.h>
#include <stdlib.h>
#ifndef PYTHON_BIN
#define PYTHON_BIN "python3"
#endif
#ifndef SELFTEST_PATH
#define SELFTEST_PATH "/mayhem/mayhem/selftest.py"
#endif
int main(void) {
    char *a[] = {(char *)PYTHON_BIN, (char *)SELFTEST_PATH, (char *)0};
    execvp(PYTHON_BIN, a);
    _exit(127);
}
