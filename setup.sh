sudo apt install python3.6 python3-pip python-pip python-wheel -y # Install python early for other things that require it.
sudo pip3 install --upgrade pip
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 1
sudo update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

pip install -r requirements.txt

sudo apt install wireshark-qt