def rcs_by_name(rcs_name):
    """Return the module for the RCS with the given name"""
    if rcs_name == "Arch":
        import arch
        return arch
    elif rcs_name == "bzr":
        import bzr
        return bzr
    elif rcs_name == "None":
        import no_rcs
        return no_rcs

def detect(dir):
    """Return the module for the rcs being used in this directory"""
    import arch
    import bzr
    if arch.detect(dir):
        return arch
    elif bzr.detect(dir):
        return bzr
    import no_rcs
    return no_rcs
