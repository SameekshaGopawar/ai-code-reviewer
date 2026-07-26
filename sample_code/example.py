import os
import subprocess


def add(a, b):
    result = a+b
    return result


def run_command(user_input):
    subprocess.call("echo " + user_input, shell=True)


class calculator:
    def __init__(self):
        self.value = 0

    def add(self, x):
        self.value = self.value + x
        return self.value
