# GUI Guide

The cash-optimizer desktop application provides a graphical interface for DraftKings optimization without the command line.

## Installation

Install with GUI dependencies:

```bash
pip install -e ".[gui]"
```

## Launching the Application

```bash
cash-optimizer-gui
```

Or from Python:

```python
from cash_optimizer_gui.app import main
main()
```

## Main Window Overview

The application has several key panels:

### Menu Bar

- **File**
  - Open CSV - Load a DraftKings export
  - Export Results - Save optimization results
  - Recent Files - Quickly reopen recent files
  - Exit - Close the application

- **View**
  - Data Panel - Toggle data information display
  - Results Panel - Toggle results display
  - Full Screen - Toggle fullscreen mode

- **Help**
  - Documentation - View online help
  - About - Application information

### Data Panel

When a CSV file is loaded, the data panel shows:

- **File Path** - Location of the loaded DraftKings export
- **Player Summary** - Counts by player status (active, injured, etc.)
- **Salary Cap & Rules** - Current lineup salary cap, position limits, team/opp limits

### Controls Panel

Main action buttons:

- **Load CSV** - Open a DraftKings player export
- **Optimize** - Calculate the optimal lineup
- **Sensitivity** - Analyze player impact
- **Simulate** - Run Monte Carlo simulation
- **Export** - Save results to disk

## Workflows

### 1. Load Data

1. Click **Load CSV** button
2. Select your DraftKings export file
3. The data panel updates showing loaded player count and salary cap

### 2. Quick Optimization

1. Load CSV file
2. Click **Optimize**
3. Results appear in the Results tab

The optimal lineup shows:
- Player names and positions
- Salary for each player
- Total salary used
- Projected point total

### 3. Sensitivity Analysis

1. Load CSV file  
2. Click **Sensitivity**
3. View results in the Results tab

Shows for each player:
- Position and salary
- Is player in optimal lineup?
- Forced-in impact (point change if forced into lineup)
- Forced-out impact (point change if forced out)
- Overall impact score

Use this to understand which players are most critical to the optimal lineup.

### 4. Simulation

1. Load CSV file
2. Click **Simulate**
3. Adjust simulation parameters in the dialog (if shown)
4. View results in the Results tab

Simulation evaluates the optimal lineup across thousands of scenarios with randomly sampled player projections.

Results include:
- Win rate at various cash thresholds
- Distribution of projected points
- Lineup robustness metrics

### 5. Export Results

1. Run optimization or simulation
2. Click **Export**
3. Choose output directory
4. Select which results to export:
   - Optimal lineup
   - Sensitivity analysis
   - Simulation results

Exports generate CSV files for analysis in Excel or other tools.

## Progress Indicators

When long-running tasks are active (optimization, simulation, export):

- **Progress Bar** - Shows percentage completion
- **Status Message** - Current operation phase
- **Cancel Button** - Abort the current task

The GUI remains responsive; you can adjust settings while tasks run.

## Results Display

The Results tab uses tabular display:

- **Column Headers** - Click to sort
- **Horizontal Scrolling** - For wide datasets
- **Row Selection** - Right-click for export options

### Copy Results

Results can be copied from the table:

1. Select rows or cells
2. Right-click → Copy
3. Paste into Excel, email, etc.

## Settings

Settings are accessible via the File menu or keyboard shortcut (Ctrl+,):

- **Solver Options**
  - Time Limit - Maximum solve time (seconds)
  - Parallelism - CPU cores to use

- **Display Options**
  - Results Format - Table or CSV preview
  - Auto-refresh - Update after each run

- **Export Options**
  - Default Directory - Where to save files
  - Include Metadata - Add timestamps and settings

## Troubleshooting

### Application Won't Start

Ensure PySide6 is installed:

```bash
pip install "PySide6>=6.7"
```

On Linux, you may need:

```bash
sudo apt-get install libqt6gui6
```

### Out of Memory

For very large slates (100+ players), reduce simulation run count or use the CLI.

### Slow Performance  

- Reduce number of simulation runs
- Use fewer candidate lineups
- Close other applications to free memory

### Results Seem Wrong

1. Verify the CSV file format matches DraftKings export
2. Check the data panel for loaded player count
3. Use --verbose in CLI for diagnostic output

## Keyboard Shortcuts

- **Ctrl+O** - Open CSV file
- **Ctrl+S** - Save results
- **Ctrl+Q** - Exit application
- **Ctrl+,** - Open settings
- **F1** - Show help
- **F11** - Toggle fullscreen

## Tips & Tricks

### Fast Iteration

1. Load a CSV once
2. Run Optimize - takes ~100ms
3. Try different players using Sensitivity
4. Export multiple lineups for comparison

### Batch Processing

For multiple slates, use the CLI instead:

```bash
for csv in *.csv; do
  cash-optimizer export "$csv" --include-sensitivity
done
```

### Performance Benchmarking

To profile the application on your hardware:

```bash
cash-optimizer benchmark players.csv --profile custom --scale 2.0
```

Then adjust GUI solver time limits accordingly.

## Advanced Features

### Custom Objective Weights

Edit the optimization objective in settings:

```
Salary Cap: 50000
Min Players: 8
Objective: maximize(projection)
```

### Constraint Editing

Add constraints via menu:
- Exclude specific players
- Force specific players into lineup
- Restrict team concentrations

### Batch Export

Export results for multiple files:

1. Load first CSV
2. Run Optimize
3. Export (creates results)
4. Load next CSV (previous results saved)
5. Repeat for multiple slates

## Getting Help

- Click **Help** → **Documentation** for online docs
- Run `cash-optimizer-gui --help` for command-line options
- Check GitHub issues at [github.com/EricTruett/cash_optimizer](https://github.com/EricTruett/cash_optimizer)
