# Fantasy-Football
Repo for Fantasy Football analysis, data scraping, visualization and modeling

![Image of Air Yards Density](https://github.com/Robert-F-Mulligan/fantasy-football/blob/master/figures/2020/05.2020/2020_Air_Yard_Density_Through5.png)

![Image of Carries Inside the 5 Chart](https://github.com/Robert-F-Mulligan/fantasy-football/blob/master/figures/sample-visualizations/2020_through_week_5_Carries_Inside_5_Yardline.png)

![Image of First Downs vs Early Down Success Rate](https://github.com/Robert-F-Mulligan/fantasy-football/blob/master/figures/sample-visualizations/2020_early_down_success_rate_and_first_downs_per_game_through_week_5.png)

![Image of Target Yardlines](https://github.com/Robert-F-Mulligan/fantasy-football/blob/master/figures/sample-visualizations/2020_through_week_5_receiver_play_yardline_breakdown.png)

![Image of Target Share vs Air Yards](https://github.com/Robert-F-Mulligan/fantasy-football/blob/master/figures/sample-visualizations/2020_through_week_5_Target_Share_vs_Air_Yard_Share.png)

![Image of Tiers Chart](https://github.com/Robert-F-Mulligan/fantasy-football/blob/master/figures/sample-visualizations/08.12.2020_rangeofrankings_gmm_QB.png)


Project Organization
------------

    │
    ├── data/               <- The original, immutable data dump. 
    │
    ├── notebooks/          <- Jupyter notebooks. 
    │
    ├── tests/               <- Unit tests.
    │
    ├── fantasyfootball/     <- Python module with source code of this project.
    │
    ├── LICENSE
    │
    ├── requirements.txt     <- pip package dependencies.   
    │
    ├── README.md            <- The top-level README for developers using this project.
    │
    └── setup.py             <- run this to install source code.
    


--------


Set up
------------

Install the virtual environment with venv and activate it:

$ python -m venv /path/to/new/virtual/environment

$ /path/to/new/virtual/environment/Scripts/activate 

Install fantasyfootball in the virtual environment by running setup.py:

$ pip install -e .

Install project dependencies through pip and requirements.txt:

$ pip install -r requrements.txt

Install a new ipython kernel:

$ ipython kernel install --user --name=fantasyfootball

Run Jupyter Notebook and open the notebooks in 'notebooks/':

$ jupyter notebook

Select the new kernel fantasyfootball

