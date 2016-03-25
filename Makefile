resultsPCT20160315.txt:
	curl http://dl.ncsbe.gov/ENRS/resultsPCT20160315.zip >resultsPCT20160315.zip
	unzip resultsPCT20160315.zip
	rm resultsPCT20160315.zip

analyze: resultsPCT20160315.txt
	./analyze.py

clean:
	rm -rf *.png