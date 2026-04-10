import re
import matplotlib.pyplot as plt
import numpy as np

# Read the data file
filename = "forces.dat"

times = []
viscous_torque_z = []

with open(filename, 'r') as f:
    for line in f:
        # Skip comment lines and empty lines
        if line.startswith('#') or not line.strip():
            continue

        # Extract time (first value on the line)
        time_match = re.match(r'\s*([\d.eE+\-]+)\s', line)
        if not time_match:
            continue
        time = float(time_match.group(1))

        # Extract all scientific notation numbers from the line
        numbers = re.findall(r'[-+]?\d*\.?\d+[eE][+-]?\d+', line)

        # Data structure per line:
        # forces_pressure(x,y,z)  forces_viscous(x,y,z)  moments_pressure(x,y,z)  moments_viscous(x,y,z)
        # indices: 0,1,2          3,4,5                   6,7,8                    9,10,11
        # Viscous torque Z = index 11
        if len(numbers) >= 12:
            viscous_torque_z_val = float(numbers[11])
            times.append(time)
            viscous_torque_z.append(viscous_torque_z_val)

times = np.array(times)
viscous_torque_z = np.array(viscous_torque_z)

# Plot
fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(times, viscous_torque_z, 'b-', linewidth=1.5, label='Viscous Torque (Z)')
ax.set_xlabel('Time (s)', fontsize=13)
ax.set_ylabel('Viscous Torque Z (N·m)', fontsize=13)
ax.set_title('Viscous Torque in Z Direction vs Time', fontsize=15)
ax.legend(fontsize=12)
ax.grid(True, linestyle='--', alpha=0.7)
plt.tight_layout()
plt.savefig('viscous_torque_z.png', dpi=150)
plt.show()
print("Plot saved as viscous_torque_z.png")
