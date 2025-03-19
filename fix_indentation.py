with open("strategy/spot_arbitrage.py", "r") as f:
    lines = f.readlines()

fixed_lines = []
for line in lines:
    if "return" in line and line.count(" ") > 12:
        spaces = " " * 12
        fixed_line = spaces + line.lstrip()
        fixed_lines.append(fixed_line)
    else:
        fixed_lines.append(line)

with open("strategy/spot_arbitrage.py", "w") as f:
    f.writelines(fixed_lines)
