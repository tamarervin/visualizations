# Parker Solar Probe

Parker Solar Probe (PSP) is a NASA mission named after Eugene Parker to study the Sun and solar wind. It takes measurements of particles, fields, and white light images
of the outer corona and near-Sun solar wind. With PSP, we are making amazing progress towards closing questions related to plasma energization and heating
in the corona and solar wind.

<div class="profile-links">
  <a href="https://psp-gateway.jhuapl.edu/">
   Parker Solar Probe Science Gateway <span aria-hidden="true">↗</span>
  </a>
  <a href="https://psp-gateway.jhuapl.edu/website/HeliophysicsScholars">
    Parker Heliophysics Scholars <span aria-hidden="true">↗</span>
  </a>
</div>

<hr class="research-divider">

## PSP Data Tutorials

PSP data can be accessed using the pySPEDAS Python package. Check out data downloading and plotting 
tutorials on my GitHub. 

<div class="profile-links">
  <a href="https://tamarervin.github.io/tutorials/">
   Data Tutorials <span aria-hidden="true">↗</span>
  </a>
</div>

<hr class="research-divider">

## Where is PSP?

PSP flies in a unique orbit, using gravity assists around Venus to get closer and closer to the Sun. The spacecraft
now has a closest approach of 9.8 solar radii (about 5% of the Earth-Sun distance). [The PSP Gateway has a great 
spacecraft tracker on their website!](https://psp-gateway.jhuapl.edu/website/Tools/SpacecraftTracker)

<figure class="psp-orbit">
  <div class="psp-orbit-readout" role="status">
    <strong data-psp-distance>Estimated position</strong>
    <span data-psp-time>Loading the ephemeris…</span>
  </div>
  <canvas width="640" height="460" role="img" aria-label="Parker Solar Probe's orbit viewed from above the J2000 ecliptic plane" hidden></canvas>
  <ul class="psp-orbit-legend" hidden>
    <li class="psp-orbit-sun">Sun</li>
    <li class="psp-orbit-past">Past path</li>
    <li class="psp-orbit-future">Future path</li>
    <li class="psp-orbit-marker">PSP</li>
  </ul>
  <figcaption>Top-down view in the J2000 ecliptic plane. Rings mark projected distances in solar radii. The readout gives the three-dimensional distance from the Sun using the <a href="https://ssd.jpl.nasa.gov/horizons/">NASA/JPL Horizons ephemeris</a>. 
  *This is the estimated position of the spacecraft, and should not be used for scientific purposes.*</figcaption>
  <noscript>Enable JavaScript to display the orbit and estimated position.</noscript>
</figure>
<script type="module" src="./psp-orbit.js"></script>


