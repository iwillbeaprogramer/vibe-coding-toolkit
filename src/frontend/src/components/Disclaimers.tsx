import { ShieldAlert } from 'lucide-react';
import type { StockDetailResponse } from '../types';

type DisclaimersProps = {
  provider?: StockDetailResponse['provider'];
};

export default function Disclaimers({ provider }: DisclaimersProps) {
  return (
    <footer className="disclaimer">
      <ShieldAlert size={17} />
      <span>
        본 애플리케이션은 투자 조언이 아닌 정보 제공 목적입니다.
        {provider ? ` ${provider.name} 기준 ${new Date(provider.fetchedAt).toLocaleString('ko-KR')}에 조회된 지연 시세입니다.` : ''}
      </span>
    </footer>
  );
}
