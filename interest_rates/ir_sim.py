from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np


@dataclass
class InterestRateSimulation:
    T: int = 100
    dt: float = 0.01
    B0: float = 0.2
    D0: float = 1
    U0: float = 0.2
    r0: float = 0.01
    rB_bar: float = 0.05  # USDC borrow rate
    rD_bar: float = 0.04  # USDC deposit rate
    beta_B: float = 0.1
    beta_D: float = 0.1
    sigma_B: float = 1
    sigma_D: float = 0.8
    u_0: float = 0.2
    k_p: float = 2
    k_d: float = 10
    u_target: float = 0.85

    def __post_init__(self):
        self.nsteps = int(self.T / self.dt)
        stats = ["delta_e", "e", "jump", "speed"]
        self.B = np.zeros(self.nsteps)
        self.D = np.zeros(self.nsteps)
        self.u = np.zeros(self.nsteps)
        self.r = np.zeros(self.nsteps)

        self.e = np.zeros(self.nsteps)
        self.delta_e = np.zeros(self.nsteps)
        self.jump = np.zeros(self.nsteps)
        self.speed = np.zeros(self.nsteps)
        # nec?
        self.stats = {k: np.zeros(self.nsteps) for k in stats}

    def simulate(self):
        B, D, u, r = self.B, self.D, self.u, self.r
        e, delta_e, speed, jump = self.e, self.delta_e, self.speed, self.jump

        B[0] = self.B0
        D[0] = self.D0
        u[0] = self.U0
        r[0] = self.r0

        b_noise = np.random.normal(size=self.nsteps + 1)
        d_noise = np.random.normal(size=self.nsteps + 1)
        for t in range(1, self.nsteps):
            db = self.beta_B * (self.rB_bar - r[t - 1]) * self.dt + (
                self.sigma_B * np.sqrt(self.dt) * b_noise[t]
            )
            dd = self.beta_D * (
                r[t - 1] * self.B[t - 1] / D[t - 1] - self.rD_bar
            ) * self.dt + (self.sigma_D * np.sqrt(self.dt) * d_noise[t])

            self.B[t] = min(self.B[t - 1] + db, D[t - 1])
            self.D[t] = D[t - 1] + dd

            self.u[t] = self.B[t] / self.D[t]

            e[t] = self.u[t] - self.u_target
            delta_e[t] = e[t] - e[t - 1]
            speed[t] = self.k_p * e[t]
            jump[t] = self.k_d ** delta_e[t]
            r[t] = r[t - 1] * jump[t] * (1 + speed[t] * self.dt)


if __name__ == "__main__":
    sim = InterestRateSimulation()
    sim.simulate()

    B, D, u, r = sim.B, sim.D, sim.u, sim.r
    time = range(len(sim.B))
    plt.figure(figsize=(14, 6))

    plt.subplot(1, 2, 1)
    plt.plot(time, u, label="Utilization (u)", color="b")
    plt.plot(time, r, label="Interest rate (r)", color="r")
    plt.axhline(y=0.85, linestyle="dotted", color="r")
    plt.xlabel("Time")
    plt.ylabel("Utilization, Interest Rate")
    plt.title("Utilization, Interest Rate Over Time")
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(time, B, label="Borrow", color="g")
    plt.plot(time, D, label="Deposit", color="b")
    plt.xlabel("Time")
    plt.ylabel("Borrow, Deposit")
    plt.title("Borrow, Deposit Over Time")
    plt.legend()

    plt.tight_layout()
    plt.show()
