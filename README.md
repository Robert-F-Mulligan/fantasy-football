# Fantasy-Football
Repo for Fantasy Football analysis, data scraping, visualization and modeling

![Image of Air Yards Density](https://github.com/Robert-F-Mulligan/fantasy-football/blob/master/figures/2020/05.2020/2020_Air_Yard_Density_Through5.png)

![Image of Tiers Chart](https://github.com/Robert-F-Mulligan/fantasy-football/blob/master/figures/08.12.2020_rangeofrankings_gmm_RB.png)


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

