# Setup
Run `sh setup.sh`. This will create the Python virtual environment and install any
necessary packages.

# Running the Sim
```
cd gauntlet
python sim.py --m {m} --beta {beta} --save_path {save_path}
```
For instance:
```
python sim.py --m 0.15 --beta 0.21 --save_path "../results/ltv.pkl"
```
