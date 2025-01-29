import os
from digidevice import config
from digidevice import cli
from DIGIHandler import DIGIHandler

def toggleSIM():
    # cfg = config.load(writable=True)
    SIMSLOTSETTING="network.modem.wwan1.sim_slot"
    cfg = config.load()
    sim_slot = cfg.get(SIMSLOTSETTING)
    print(f"Sim slot is {sim_slot} {type(sim_slot)}")
    nsim_slot = "2" if sim_slot == "1" else "1"
    cfg = config.load(writable=True)
    cfg.set(SIMSLOTSETTING,nsim_slot)
    cfg.commit()
    sim_slot = cfg.get(SIMSLOTSETTING)
    print(f"Sim slot is {sim_slot}")

def main():
    dh = DIGIHandler(mode = "DIGIDEVICE")
    
    toggleSIM()


if __name__ == '__main__': main()