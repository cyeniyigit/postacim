"""Sertifika zinciri onarımı testleri (çevrimdışı).

AIA çözümleme, PEM çevirisi, birleşik CA yazımı (0600) ve bağlam üretimi
sahte girdilerle doğrulanır; ağ erişimi YOK.
"""

import base64
import os
import ssl
import sys
import tempfile
import unittest
from unittest import mock

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from postacim import sertifika  # noqa: E402

SAHTE_YAPRAK_PEM = """-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAKZbYBhCQ4O5MA0GCSqGSIb3DQEBCwUAMBsxGTAXBgNVBAUTEHNh
aGlwZWQud2lraXBhZ2VzMQ==
-----END CERTIFICATE-----
"""


def _pem_icerir(dosya, parca):
    metin = open(dosya, encoding="utf-8").read()
    return parca in metin


class PemTest(unittest.TestCase):
    def test_duz_pem_degismez(self):
        self.assertEqual(sertifika._pem_yap(SAHTE_YAPRAK_PEM.encode()),
                         SAHTE_YAPRAK_PEM)

    def test_der_pem_yapilir(self):
        der = base64.b64decode(
            "MIIBkTCB+wIJAKZbYBhCQ4O5MA0GCSqGSIb3DQEBCwUAMBsxGTAXBgNVBAUTEHNh"
            "aGlwZWQud2lraXBhZ2VzMQ=="
        )
        pem = sertifika._pem_yap(der)
        self.assertTrue(pem.startswith("-----BEGIN CERTIFICATE-----"))
        self.assertTrue(pem.rstrip().endswith("-----END CERTIFICATE-----"))


class AiaTest(unittest.TestCase):
    def test_aia_adresi_cozulur(self):
        cikti = (
            "Authority Information Access: \n"
            "    CA Issuers - URI:http://secure.ornek.com/cacert/ara.crt\n"
            "    OCSP - URI:http://ocsp.ornek.com\n"
        ).encode()
        sahte = mock.Mock(returncode=0, stdout=cikti)
        with mock.patch.object(sertifika.subprocess, "run", return_value=sahte):
            adresler = sertifika._aia_adresleri(SAHTE_YAPRAK_PEM)
        self.assertEqual(adresler, ["http://secure.ornek.com/cacert/ara.crt"])

    def test_openssl_yoksa_bos(self):
        with mock.patch.object(sertifika.shutil, "which", return_value=None):
            self.assertEqual(sertifika._aia_adresleri(SAHTE_YAPRAK_PEM), [])


class ZincirOnarTest(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        self.eski_state = sertifika.STATE_DIZIN
        self.eski_ca = sertifika.CA_DOSYA
        sertifika.STATE_DIZIN = self.dizin
        sertifika.CA_DOSYA = os.path.join(self.dizin, "sertifika_ca.pem")

    def tearDown(self):
        sertifika.STATE_DIZIN = self.eski_state
        sertifika.CA_DOSYA = self.eski_ca

    def test_onarim_birlesik_dosya_yazar(self):
        taban = os.path.join(self.dizin, "taban.pem")
        with open(taban, "w") as f:
            f.write("# kök CA depoları\n")
        ara_pem = SAHTE_YAPRAK_PEM + "\n"  # sahte ara
        with mock.patch.object(sertifika, "_served_certs",
                               return_value=[SAHTE_YAPRAK_PEM]), \
             mock.patch.object(sertifika, "_ca_tabani", return_value=taban), \
             mock.patch.object(
                 sertifika, "_ara_sertifikalari_coz", return_value=[ara_pem]):
            dosya = sertifika.zinciri_onar("ornek", 993)
        self.assertEqual(dosya, sertifika.CA_DOSYA)
        self.assertTrue(_pem_icerir(dosya, "kök CA depoları"))
        self.assertTrue(_pem_icerir(dosya, "MIIBkTCB+wIJAKZb"))
        self.assertEqual(os.stat(dosya).st_mode & 0o777, 0o600)

    def test_sunucu_sertifikasi_vermezse_none(self):
        with mock.patch.object(sertifika, "_served_certs", return_value=[]):
            self.assertIsNone(sertifika.zinciri_onar("ornek", 993))

    def test_baglan_dene_onarilamayan(self):
        with mock.patch.object(sertifika, "zinciri_onar", return_value=None):
            self.assertIsNone(sertifika.baglan_dene("ornek", 993))

    def test_baglan_dene_baglam_uretir(self):
        # Gerçek sistem CA deposuyla geçerli bağlam (doğrulama açık)
        dosya = sertifika._ca_tabani()
        if not dosya or not os.path.exists(dosya):
            self.skipTest("sistem CA deposu yok")
        ctx = sertifika.baglam(dosya)
        self.assertIsInstance(ctx, ssl.SSLContext)
        self.assertNotEqual(ctx.verify_mode, ssl.CERT_NONE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
