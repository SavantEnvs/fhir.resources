/* Thin ELF launcher: Mayhem requires an ELF target, so this execs python3 on the atheris
 * harness, forwarding all libFuzzer args. exec replaces the image, so the running process
 * IS the atheris/libFuzzer harness (transparent to Mayhem). */
#include <unistd.h>
#include <stdlib.h>
#ifndef PYTHON_BIN
#define PYTHON_BIN "python3"
#endif
#ifndef SCRIPT_PATH
#define SCRIPT_PATH "/mayhem/mayhem/fuzz_resource_creation.py"
#endif
int main(int argc, char **argv) {
    char **a = (char **)calloc((size_t)argc + 3, sizeof(char *));
    int n = 0;
    a[n++] = (char *)PYTHON_BIN;
    a[n++] = (char *)SCRIPT_PATH;
    for (int i = 1; i < argc; i++) a[n++] = argv[i];
    a[n] = (char *)0;
    execvp(PYTHON_BIN, a);
    _exit(127);
}
