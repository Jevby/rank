sudo add-apt-repository -y ppa:jonathonf/python-3.6
sudo apt-get update
sudo apt-get install -y python3.6 python3-pip nginx
sudo -H python3.6 -m pip install sqlalchemy pyquery
sudo ln -s /var/www/rank/misc/rank.service /etc/systemd/system/rank.service