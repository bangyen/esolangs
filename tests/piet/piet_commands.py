"""Piet stack rules from David Morgan-Mar's command specification."""


def command(change, size, values):
    stack = list(values)
    dp = cc = 0
    effect = None
    hue, light = change
    if (hue, light) == (0, 1):
        stack.append(size)
    elif (hue, light) == (0, 2):
        if stack:
            stack.pop()
    elif hue in (1, 2, 3) and (hue, light) not in ((2, 2), (3, 1), (3, 2)):
        if len(stack) >= 2:
            a, b = stack[-2:]
            if hue == 1:
                answer = (a + b, a - b, a * b)[light]
            elif hue == 2:
                if b == 0:
                    return (tuple(stack), dp, cc, effect)
                answer = a // b if light == 0 else a % b
            else:
                answer = int(a > b)
            stack[-2:] = [answer]
    elif (hue, light) == (2, 2):
        if stack:
            stack[-1] = int(stack[-1] == 0)
    elif hue == 3:
        if stack:
            value = stack.pop()
            if light == 1:
                dp = value
            else:
                cc = abs(value) % 2
    elif (hue, light) == (4, 0):
        if stack:
            stack.append(stack[-1])
    elif (hue, light) == (4, 1):
        if len(stack) >= 2:
            depth, rolls = stack[-2:]
            if 0 < depth <= len(stack) - 2:
                del stack[-2:]
                for _ in range(rolls % depth):
                    top = stack.pop()
                    stack.insert(len(stack) - depth + 1, top)
    elif (hue, light) == (4, 2):
        effect = ("number", 0)
    elif (hue, light) == (5, 0):
        effect = ("char", 0)
    elif hue == 5 and stack:
        value = stack.pop()
        effect = ("out_number" if light == 1 else "out_char", value)
    return (tuple(stack), dp, cc, effect)
