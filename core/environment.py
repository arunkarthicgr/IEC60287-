# Soil classification reference values and ambient condition helpers

SOIL_CLASSES = {
    'dry':    2.5,   # K.m/W  — bone-dry sand/gravel
    'normal': 1.2,   # typical backfill
    'moist':  0.9,   # moist clay
    'wet':    0.7,   # saturated soil
}


def describe_soil(rho_soil):
    """Return a descriptive label for a given soil thermal resistivity."""
    if rho_soil >= 2.0:
        return "dry"
    elif rho_soil >= 1.1:
        return "normal"
    elif rho_soil >= 0.8:
        return "moist"
    else:
        return "wet"


def delta_theta(theta_max, theta_amb):
    """Permissible temperature rise (K) used in the ampacity formula."""
    return theta_max - theta_amb
