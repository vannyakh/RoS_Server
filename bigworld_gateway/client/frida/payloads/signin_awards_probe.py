# READ-ONLY: award ids of the daily sign-in table and DTS_SIGN_IN_AWARD_MAX.
import sys
out = open(OUT, 'w')
try:
    import shared, const
    lp = sys.modules.get('legacyProperties') or getattr(shared, 'legacyProperties', None)
    for k, v in lp.iterDtsSigninData():
        out.write('day %r awardID=%r release=%r\n' % (k, v.awardID, getattr(v, 'release_type', None)))
    out.write('DTS_SIGN_IN_AWARD_MAX=%r\n' % getattr(const, 'DTS_SIGN_IN_AWARD_MAX', None))
except Exception:
    import traceback; out.write(traceback.format_exc())
out.close()
