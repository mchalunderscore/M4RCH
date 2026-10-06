.POSIX:
KDIR = /lib/modules/7.1.3-m4rch/build
obj-m = m4rch_gpu_adt.o
all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) modules
clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) clean
