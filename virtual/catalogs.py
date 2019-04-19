# coding=utf-8

import logging
import math

from marblecutter import Bounds, get_resolution_in_meters, get_source, get_zoom
from marblecutter.catalogs import WGS84_CRS, Catalog
from marblecutter.utils import Source
from rasterio import warp
from rasterio.enums import Resampling

LOG = logging.getLogger(__name__)

def to_camel_case(snake_str):
    components = snake_str.split('_')
    # We capitalize the first letter of each component except the first one
    # with the 'title' method and join them together.
    return components[0].lower() + ''.join(x.title() for x in components[1:])

# Camel cases all top level keys in the dictionary, does not handle
# sub dictionaries
def snake_case_to_camel_case_keys_of_dict(old_dict):
    kv = old_dict.items()
    new_dict = {}
    for k, v in kv:
        new_dict[to_camel_case(k)] = v
    return new_dict

class VirtualCatalog(Catalog):
    _rgb = None
    _nodata = None
    _linear_stretch = None
    _resample = None

    def __init__(self, uri, rgb=None, nodata=None, linear_stretch=None, resample=None, 
        dst_max=None, dst_min=None, force_cast=None, to_vis=None):
        self._uri = uri
        self._dst_min = dst_min
        self._dst_max = dst_max
        self._force_cast = force_cast
        self._to_vis = to_vis

        if rgb:
            self._rgb = rgb

        if nodata:
            self._nodata = nodata

        if linear_stretch:
            self._linear_stretch = linear_stretch
        
        try:
            # test whether provided resampling method is valid
            Resampling[resample]
            self._resample = resample
        except KeyError:
            self._resample = None

        self._meta = {}
        self.src_meta = {}

        with get_source(self._uri) as src:
            self.src_meta = snake_case_to_camel_case_keys_of_dict(src.tags())
            self.src_meta["bandCount"] = src.count
            self._bounds = warp.transform_bounds(src.crs, WGS84_CRS, *src.bounds)
            self._resolution = get_resolution_in_meters(
                Bounds(src.bounds, src.crs), (src.height, src.width)
            )
            approximate_zoom = get_zoom(max(self._resolution), op=math.ceil)
            
            global_min = src.get_tag_item("TIFFTAG_MINSAMPLEVALUE")
            global_max = src.get_tag_item("TIFFTAG_MAXSAMPLEVALUE")

            band_order = src.get_tag_item("BAND_ORDER")
            if str(self._rgb).lower() == "metadata":
                if band_order is not None:
                    band_order = band_order.split(',')
                    def get_band_from_band_order(band_order, band_name, fallback):
                        if band_name in band_order:
                            return str(band_order.index(band_name) + 1)
                        else:
                            return fallback
                    red_band = get_band_from_band_order(band_order, "RED", "1")
                    green_band = get_band_from_band_order(band_order, "GRE", "2")
                    blue_band = get_band_from_band_order(band_order, "BLU", "3")
                    self._rgb = ",".join([red_band, green_band, blue_band])
                else:
                    # Fallback
                    if src.count >= 3:
                        self._rgb = "1,2,3"
                    else:
                        self._rgb = "1,1,1"
            
            self.src_meta["bandMetadata"] = {}
            # FarmLens specific
            band_assignments = band_order
            if band_order is None:
                band_assignments = range(0, src.count)
            for band in range(0, src.count):
                self.src_meta["bandMetadata"][band_assignments[band]] = snake_case_to_camel_case_keys_of_dict(src.tags(bidx=band+1))
                self._meta["values"] = self._meta.get("values", {})
                self._meta["values"][band] = {}
                min_val = src.get_tag_item("STATISTICS_MINIMUM", bidx=band + 1)
                max_val = src.get_tag_item("STATISTICS_MAXIMUM", bidx=band + 1)
                mean_val = src.get_tag_item("STATISTICS_MEAN", bidx=band + 1)
                stddev_val = src.get_tag_item("STATISTICS_STDDEV", bidx=band + 1)
                
                if min_val is not None:
                    self._meta["values"][band]["min"] = float(min_val)
                elif global_min is not None:
                    self._meta["values"][band]["min"] = float(global_min)

                if max_val is not None:
                    self._meta["values"][band]["max"] = float(max_val)
                elif global_max is not None:
                    self._meta["values"][band]["max"] = float(global_max)

                if mean_val is not None:
                    self._meta["values"][band]["mean"] = float(mean_val)

                if stddev_val is not None:
                    self._meta["values"][band]["stddev"] = float(stddev_val)

        self._center = [
            (self._bounds[0] + self.bounds[2]) / 2,
            (self._bounds[1] + self.bounds[3]) / 2,
            approximate_zoom - 3,
        ]
        self._maxzoom = approximate_zoom + 3
        self._minzoom = approximate_zoom - 10

    @property
    def uri(self):
        return self._uri

    def get_sources(self, bounds, resolution):
        recipes = {"imagery": True}

        if self._rgb is not None:
            recipes["rgb_bands"] = map(int, self._rgb.split(","))

        if self._nodata is not None:
            recipes["nodata"] = self._nodata

        if self._linear_stretch is not None:
            valid_values = ["per_band", "global", "if_needed"]
            if self._linear_stretch not in valid_values:
                self._linear_stretch = valid_values[0]
                LOG.debug("No specific linear_stretch passed, using: {0}".format(self._linear_stretch))
            recipes["linear_stretch"] = self._linear_stretch

        if self._resample is not None:
            recipes["resample"] = self._resample

        if self._to_vis is not None:
            recipes["dst_min"] = 0
            recipes["dst_max"] = 255
            recipes["force_cast"] = 'uint8'

        if self._dst_min is not None:
            recipes["dst_min"] = self._dst_min
        
        if self._dst_max is not None:
            recipes["dst_max"] = self._dst_max

        if self._force_cast is not None:
            recipes["force_cast"] = self._force_cast

        yield Source(
            url=self._uri,
            name=self._name,
            resolution=self._resolution,
            band_info={},
            meta=self._meta,
            recipes=recipes,
        )
