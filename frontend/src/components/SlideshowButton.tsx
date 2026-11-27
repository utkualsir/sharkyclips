// 1.2.72: the "Photo slideshow" button of the home screens (Easy and Pro).
import { useI18n } from "../i18n";
import { href } from "../router";
import { Icon } from "./Icons";
import "../slideshow.css";

export function SlideshowButton() {
  const { t } = useI18n();
  return (
    <a className="ss-home-card" href={href.slideshows} data-testid="slideshow-home">
      <span className="ss-home-icon" aria-hidden="true">
        <Icon name="image" size={22} />
      </span>
      <span className="ss-home-text">
        <b>{t("slideshow.home_title")}</b>
        <span>{t("slideshow.home_hint")}</span>
      </span>
      <Icon name="chevron-right" size={18} className="flip-rtl" />
    </a>
  );
}
